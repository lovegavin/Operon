//! Pure close/update lifecycle state machine.
//!
//! This module performs no I/O, spawns nothing and waits for nothing. Hiding the
//! window is deliberately separate from beginning a full exit. A close request
//! mints one UUID; repeated close requests while flushing coalesce onto that
//! same ID. A stale acknowledgement never changes state. A failed draft save or
//! a draft/flush timeout restores the visible ready state and records a typed
//! failure. A drain timeout enters `Recovery`; only confirmed process exit can
//! move the lifecycle to `Closed`.

use crate::error::{HostError, HostNextAction};
use uuid::Uuid;

/// Explicit lifecycle states from the shared native contract.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum LifecycleState {
    Starting,
    ReadyVisible,
    ReadyHidden,
    Flushing { request_id: String },
    Draining,
    Recovery,
    BackendFailed,
    Closed,
}

/// A repeated close request coalesces onto the original request ID.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct CloseRequest {
    pub request_id: String,
    pub coalesced: bool,
}

/// Outcome of a renderer draft-flush acknowledgement.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum FlushOutcome {
    Visible,
    Draining,
}

/// Failure that leaves the window usable or waiting for an explicit retry.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum CloseFailure {
    DraftTimeout,
    DrainTimeout,
}

/// Pure state machine for one host session.
#[derive(Debug, Clone)]
pub struct Lifecycle {
    state: LifecycleState,
    last_request_id: Option<String>,
    failure: Option<CloseFailure>,
}

impl Default for Lifecycle {
    fn default() -> Self {
        Self::new()
    }
}

impl Lifecycle {
    pub fn new() -> Self {
        Self {
            state: LifecycleState::Starting,
            last_request_id: None,
            failure: None,
        }
    }

    pub fn state(&self) -> &LifecycleState {
        &self.state
    }

    pub fn request_id(&self) -> Option<&str> {
        match &self.state {
            LifecycleState::Flushing { request_id } => Some(request_id.as_str()),
            _ => self.last_request_id.as_deref(),
        }
    }

    pub fn failure(&self) -> Option<CloseFailure> {
        self.failure
    }

    /// The backend reported authenticated readiness.
    pub fn mark_ready(&mut self) -> Result<(), HostError> {
        match self.state {
            LifecycleState::Starting => {
                self.state = LifecycleState::ReadyVisible;
                Ok(())
            }
            LifecycleState::ReadyVisible | LifecycleState::ReadyHidden => Ok(()),
            _ => Err(HostError::request_stale(None)),
        }
    }

    /// Hide to tray/shortcut. This does not begin a full exit.
    pub fn hide(&mut self) -> Result<(), HostError> {
        match self.state {
            LifecycleState::ReadyVisible => {
                self.state = LifecycleState::ReadyHidden;
                Ok(())
            }
            LifecycleState::ReadyHidden => Ok(()),
            _ => Err(HostError::request_stale(None)),
        }
    }

    /// Show a previously hidden window. This does not restart a backend.
    pub fn show(&mut self) -> Result<(), HostError> {
        match self.state {
            LifecycleState::ReadyHidden => {
                self.state = LifecycleState::ReadyVisible;
                Ok(())
            }
            LifecycleState::ReadyVisible => Ok(()),
            _ => Err(HostError::request_stale(None)),
        }
    }

    /// Begin a full exit, or coalesce with the close already in flight.
    ///
    /// `Recovery` intentionally requires an explicit shutdown retry at the
    /// backend layer; this method reports that as retryable rather than minting
    /// a second request or claiming success.
    pub fn begin_close(&mut self) -> Result<CloseRequest, HostError> {
        match &self.state {
            LifecycleState::ReadyVisible | LifecycleState::ReadyHidden => {
                let request_id = Uuid::new_v4().to_string();
                self.last_request_id = Some(request_id.clone());
                self.failure = None;
                self.state = LifecycleState::Flushing {
                    request_id: request_id.clone(),
                };
                Ok(CloseRequest {
                    request_id,
                    coalesced: false,
                })
            }
            LifecycleState::Flushing { request_id } => Ok(CloseRequest {
                request_id: request_id.clone(),
                coalesced: true,
            }),
            LifecycleState::Draining => match self.last_request_id.clone() {
                Some(request_id) => Ok(CloseRequest {
                    request_id,
                    coalesced: true,
                }),
                None => Err(HostError::request_stale(None)),
            },
            LifecycleState::Recovery => Err(HostError::capability_unavailable(
                HostNextAction::Retry,
                None,
            )),
            LifecycleState::Starting | LifecycleState::BackendFailed | LifecycleState::Closed => {
                Err(HostError::request_stale(None))
            }
        }
    }

    /// Apply the renderer draft-flush acknowledgement. A wrong or stale ID is
    /// rejected without changing state.
    pub fn acknowledge_draft_flush(
        &mut self,
        request_id: &str,
        saved: bool,
    ) -> Result<FlushOutcome, HostError> {
        let LifecycleState::Flushing {
            request_id: current,
        } = &self.state
        else {
            return Err(HostError::request_stale(Some(request_id.to_owned())));
        };
        if current.as_str() != request_id {
            return Err(HostError::request_stale(Some(request_id.to_owned())));
        }

        if saved {
            self.state = LifecycleState::Draining;
            Ok(FlushOutcome::Draining)
        } else {
            self.state = LifecycleState::ReadyVisible;
            self.last_request_id = None;
            self.failure = None;
            Ok(FlushOutcome::Visible)
        }
    }

    /// The renderer did not answer the draft flush in time. Restore the visible
    /// window and report a failure; the exit is not treated as successful.
    pub fn draft_flush_timed_out(&mut self, request_id: &str) -> Result<(), HostError> {
        if !Self::is_current_flush(&self.state, request_id) {
            return Err(HostError::request_stale(Some(request_id.to_owned())));
        }
        self.state = LifecycleState::ReadyVisible;
        self.last_request_id = None;
        self.failure = Some(CloseFailure::DraftTimeout);
        Ok(())
    }

    /// The owned process did not stop within the drain deadline. Enter
    /// `Recovery`; this state is not `Closed` and does not claim success.
    pub fn drain_timed_out(&mut self) -> Result<(), HostError> {
        if self.state != LifecycleState::Draining {
            return Err(HostError::request_stale(None));
        }
        self.state = LifecycleState::Recovery;
        self.failure = Some(CloseFailure::DrainTimeout);
        Ok(())
    }

    /// The owned child exited unexpectedly outside a close flow. A
    /// drain/recovery caller already has a close in flight and must confirm
    /// actual stop through [`Lifecycle::backend_stopped`] instead.
    pub fn backend_failed(&mut self) -> Result<(), HostError> {
        match self.state {
            LifecycleState::Starting
            | LifecycleState::ReadyVisible
            | LifecycleState::ReadyHidden
            | LifecycleState::Flushing { .. } => {
                self.state = LifecycleState::BackendFailed;
                Ok(())
            }
            LifecycleState::Draining | LifecycleState::Recovery => {
                Err(HostError::request_stale(None))
            }
            LifecycleState::BackendFailed | LifecycleState::Closed => Ok(()),
        }
    }

    /// Confirm that the owned child stopped. This is the only transition to
    /// `Closed` for a drain/recovery flow; a timeout alone cannot reach it.
    pub fn backend_stopped(&mut self) -> Result<(), HostError> {
        match self.state {
            LifecycleState::Draining | LifecycleState::Recovery | LifecycleState::BackendFailed => {
                self.state = LifecycleState::Closed;
                self.last_request_id = None;
                Ok(())
            }
            LifecycleState::Closed => Ok(()),
            _ => Err(HostError::request_stale(None)),
        }
    }

    fn is_current_flush(state: &LifecycleState, request_id: &str) -> bool {
        matches!(state, LifecycleState::Flushing { request_id: current } if current.as_str() == request_id)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn ready() -> Lifecycle {
        let mut lifecycle = Lifecycle::new();
        lifecycle.mark_ready().unwrap();
        lifecycle
    }

    #[test]
    fn hide_and_show_do_not_begin_exit() {
        let mut lifecycle = ready();
        lifecycle.hide().unwrap();
        assert_eq!(lifecycle.state(), &LifecycleState::ReadyHidden);
        assert_eq!(lifecycle.request_id(), None);
        lifecycle.show().unwrap();
        assert_eq!(lifecycle.state(), &LifecycleState::ReadyVisible);
    }

    #[test]
    fn close_mints_uuid_and_repeats_coalesce() {
        let mut lifecycle = ready();
        let first = lifecycle.begin_close().unwrap();
        assert!(!first.coalesced);
        assert!(Uuid::parse_str(&first.request_id).is_ok());

        let second = lifecycle.begin_close().unwrap();
        assert!(second.coalesced);
        assert_eq!(first.request_id, second.request_id);
        assert_eq!(lifecycle.request_id(), Some(first.request_id.as_str()));
    }

    #[test]
    fn stale_acknowledgement_is_rejected_without_state_change() {
        let mut lifecycle = ready();
        let request = lifecycle.begin_close().unwrap();
        let error = lifecycle
            .acknowledge_draft_flush("not-the-request", true)
            .unwrap_err();
        assert_eq!(error.code(), crate::error::HostErrorCode::HostRequestStale);
        assert!(matches!(lifecycle.state(), LifecycleState::Flushing { .. }));
        assert_eq!(lifecycle.request_id(), Some(request.request_id.as_str()));
    }

    #[test]
    fn save_false_restores_visible() {
        let mut lifecycle = ready();
        lifecycle.hide().unwrap();
        let request = lifecycle.begin_close().unwrap();
        let outcome = lifecycle
            .acknowledge_draft_flush(&request.request_id, false)
            .unwrap();
        assert_eq!(outcome, FlushOutcome::Visible);
        assert_eq!(lifecycle.state(), &LifecycleState::ReadyVisible);
    }

    #[test]
    fn saved_moves_to_draining_then_stopped_closes() {
        let mut lifecycle = ready();
        let request = lifecycle.begin_close().unwrap();
        let outcome = lifecycle
            .acknowledge_draft_flush(&request.request_id, true)
            .unwrap();
        assert_eq!(outcome, FlushOutcome::Draining);
        assert_eq!(lifecycle.state(), &LifecycleState::Draining);
        lifecycle.backend_stopped().unwrap();
        assert_eq!(lifecycle.state(), &LifecycleState::Closed);
    }

    #[test]
    fn draft_timeout_restores_visible_with_failure() {
        let mut lifecycle = ready();
        let request = lifecycle.begin_close().unwrap();
        lifecycle
            .draft_flush_timed_out(&request.request_id)
            .unwrap();
        assert_eq!(lifecycle.state(), &LifecycleState::ReadyVisible);
        assert_eq!(lifecycle.failure(), Some(CloseFailure::DraftTimeout));
    }

    #[test]
    fn drain_timeout_enters_recovery_not_closed() {
        let mut lifecycle = ready();
        let request = lifecycle.begin_close().unwrap();
        lifecycle
            .acknowledge_draft_flush(&request.request_id, true)
            .unwrap();
        lifecycle.drain_timed_out().unwrap();
        assert_eq!(lifecycle.state(), &LifecycleState::Recovery);
        assert_eq!(lifecycle.failure(), Some(CloseFailure::DrainTimeout));
    }

    #[test]
    fn recovery_closes_only_after_confirmed_stop() {
        let mut lifecycle = ready();
        let request = lifecycle.begin_close().unwrap();
        lifecycle
            .acknowledge_draft_flush(&request.request_id, true)
            .unwrap();
        lifecycle.drain_timed_out().unwrap();
        assert_eq!(lifecycle.state(), &LifecycleState::Recovery);
        assert!(lifecycle.backend_failed().is_err());
        assert_eq!(lifecycle.state(), &LifecycleState::Recovery);
        lifecycle.backend_stopped().unwrap();
        assert_eq!(lifecycle.state(), &LifecycleState::Closed);
    }

    #[test]
    fn repeated_close_while_draining_is_coalesced() {
        let mut lifecycle = ready();
        let request = lifecycle.begin_close().unwrap();
        lifecycle
            .acknowledge_draft_flush(&request.request_id, true)
            .unwrap();
        let repeated = lifecycle.begin_close().unwrap();
        assert!(repeated.coalesced);
        assert_eq!(repeated.request_id, request.request_id);
        assert_eq!(lifecycle.state(), &LifecycleState::Draining);
    }

    #[test]
    fn close_during_startup_is_rejected() {
        let mut lifecycle = Lifecycle::new();
        assert!(lifecycle.begin_close().is_err());
        assert_eq!(lifecycle.state(), &LifecycleState::Starting);
    }
}
