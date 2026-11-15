//! Stable host error DTO shared with `frontend/src/host/types.ts`.
//!
//! Every host failure is one of the four TypeScript codes with a fixed, safe
//! message. Constructors never copy arbitrary exception text into `message`.

use serde::{Deserialize, Serialize};
use std::fmt;

/// `HostErrorShape.message` for `host_unsupported`.
pub const UNSUPPORTED_MESSAGE: &str = "This desktop host operation is not supported.";
/// `HostErrorShape.message` for `host_capability_unavailable`.
pub const CAPABILITY_UNAVAILABLE_MESSAGE: &str = "This desktop host capability is unavailable.";
/// `HostErrorShape.message` for `host_request_stale`.
pub const REQUEST_STALE_MESSAGE: &str = "The desktop host request is stale.";
/// `HostErrorShape.message` for `host_bridge_unavailable`; matches the TypeScript
/// `toHostError` fallback exactly.
pub const BRIDGE_UNAVAILABLE_MESSAGE: &str = "Desktop host bridge failed.";

/// The four stable host error codes from the shared contract.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum HostErrorCode {
    HostUnsupported,
    HostCapabilityUnavailable,
    HostRequestStale,
    HostBridgeUnavailable,
}

impl HostErrorCode {
    /// The only message this code may carry.
    pub const fn message(self) -> &'static str {
        match self {
            Self::HostUnsupported => UNSUPPORTED_MESSAGE,
            Self::HostCapabilityUnavailable => CAPABILITY_UNAVAILABLE_MESSAGE,
            Self::HostRequestStale => REQUEST_STALE_MESSAGE,
            Self::HostBridgeUnavailable => BRIDGE_UNAVAILABLE_MESSAGE,
        }
    }
}

/// The four stable recovery hints from the shared contract.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum HostNextAction {
    UseTrayMenuExit,
    OpenHostLogs,
    UseHttpArtifactLink,
    Retry,
}

/// Serialized host error with exactly the five TypeScript contract fields.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(try_from = "HostErrorWire")]
pub struct HostError {
    code: HostErrorCode,
    message: String,
    request_id: Option<String>,
    retryable: bool,
    next_actions: Vec<HostNextAction>,
}

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct HostErrorWire {
    code: HostErrorCode,
    message: String,
    request_id: Option<String>,
    retryable: bool,
    next_actions: Vec<HostNextAction>,
}

impl TryFrom<HostErrorWire> for HostError {
    type Error = String;

    fn try_from(wire: HostErrorWire) -> Result<Self, Self::Error> {
        let expected_message = wire.code.message();
        if wire.message != expected_message {
            return Err("host error message is not a canonical host message".to_owned());
        }
        let request_id = match wire.request_id {
            Some(id) if id.is_empty() => {
                return Err("host error request_id must be non-empty or null".to_owned())
            }
            id => id,
        };
        let retryable = wire.code == HostErrorCode::HostCapabilityUnavailable
            && wire.next_actions.contains(&HostNextAction::Retry);
        if wire.retryable != retryable {
            return Err("host error retryable does not match its code and next actions".to_owned());
        }
        let actions_match_code = match wire.code {
            HostErrorCode::HostCapabilityUnavailable => !wire.next_actions.is_empty(),
            _ => wire.next_actions.is_empty(),
        };
        if !actions_match_code {
            return Err("host error next_actions do not match its code".to_owned());
        }
        Ok(Self {
            code: wire.code,
            message: expected_message.to_owned(),
            request_id,
            retryable,
            next_actions: wire.next_actions,
        })
    }
}

impl HostError {
    fn new(
        code: HostErrorCode,
        request_id: Option<String>,
        retryable: bool,
        next_actions: Vec<HostNextAction>,
    ) -> Self {
        Self {
            code,
            message: code.message().to_owned(),
            request_id: normalize_request_id(request_id),
            retryable,
            next_actions,
        }
    }

    /// The operation is not implemented by this host.
    pub fn unsupported(request_id: Option<String>) -> Self {
        Self::new(
            HostErrorCode::HostUnsupported,
            request_id,
            false,
            Vec::new(),
        )
    }

    /// A typed operation has no host implementation yet.
    pub fn capability_unavailable(action: HostNextAction, request_id: Option<String>) -> Self {
        Self::new(
            HostErrorCode::HostCapabilityUnavailable,
            request_id,
            action == HostNextAction::Retry,
            vec![action],
        )
    }

    /// The request ID is unknown, duplicate, stale or already unsubscribed.
    pub fn request_stale(request_id: Option<String>) -> Self {
        Self::new(
            HostErrorCode::HostRequestStale,
            request_id,
            false,
            Vec::new(),
        )
    }

    /// The bridge itself failed. The message matches the TypeScript fallback.
    pub fn bridge_unavailable() -> Self {
        Self::new(
            HostErrorCode::HostBridgeUnavailable,
            None,
            false,
            Vec::new(),
        )
    }

    /// Attach or replace a non-empty correlation ID.
    pub fn with_request_id(mut self, request_id: impl Into<String>) -> Self {
        self.request_id = normalize_request_id(Some(request_id.into()));
        self
    }

    pub fn code(&self) -> HostErrorCode {
        self.code
    }

    pub fn message(&self) -> &str {
        &self.message
    }

    pub fn request_id(&self) -> Option<&str> {
        self.request_id.as_deref()
    }

    pub fn retryable(&self) -> bool {
        self.retryable
    }

    pub fn next_actions(&self) -> &[HostNextAction] {
        &self.next_actions
    }
}

impl fmt::Display for HostError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.write_str(&self.message)
    }
}

impl std::error::Error for HostError {}

fn normalize_request_id(request_id: Option<String>) -> Option<String> {
    request_id.filter(|id| !id.is_empty())
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    #[test]
    fn serializes_exact_contract_fields() {
        let error = HostError::request_stale(Some("request-1".to_owned()));
        assert_eq!(
            serde_json::to_value(&error).unwrap(),
            json!({
                "code": "host_request_stale",
                "message": REQUEST_STALE_MESSAGE,
                "request_id": "request-1",
                "retryable": false,
                "next_actions": []
            })
        );
    }

    #[test]
    fn bridge_failure_matches_typescript_fallback() {
        let value = serde_json::to_value(HostError::bridge_unavailable()).unwrap();
        assert_eq!(value["code"], json!("host_bridge_unavailable"));
        assert_eq!(value["message"], json!("Desktop host bridge failed."));
        assert_eq!(value["request_id"], serde_json::Value::Null);
    }

    #[test]
    fn retry_capability_is_retryable() {
        let value = serde_json::to_value(HostError::capability_unavailable(
            HostNextAction::Retry,
            None,
        ))
        .unwrap();
        assert_eq!(value["retryable"], json!(true));
        assert_eq!(value["next_actions"], json!(["retry"]));
    }

    #[test]
    fn empty_request_id_is_normalized_to_null() {
        let error = HostError::request_stale(Some(String::new())).with_request_id("");
        assert_eq!(error.request_id(), None);
    }

    #[test]
    fn rejects_foreign_messages() {
        let wire = r#"{"code":"host_bridge_unavailable","message":"C:\\secret\\path","request_id":null,"retryable":false,"next_actions":[]}"#;
        assert!(serde_json::from_str::<HostError>(wire).is_err());
    }

    #[test]
    fn rejects_empty_request_id_on_the_wire() {
        let wire = r#"{"code":"host_request_stale","message":"The desktop host request is stale.","request_id":"","retryable":false,"next_actions":[]}"#;
        assert!(serde_json::from_str::<HostError>(wire).is_err());
    }
}
