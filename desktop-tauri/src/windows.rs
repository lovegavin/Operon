//! Owned-process lifetime primitives.
//!
//! On Windows the management service is assigned to one Job Object created with
//! exactly the same limits as the existing C# host:
//! `KILL_ON_JOB_CLOSE | BREAKAWAY_OK`. Closing the job handle when the host
//! really dies terminates the owned service tree; a child that explicitly asks
//! to break away (the existing shared pool/viewer helpers) is allowed to leave
//! the job and survive. No process-name based cleanup is performed here.

use crate::error::HostError;
use tokio::process::Child;

#[cfg(windows)]
pub struct JobObject {
    handle: usize,
}

#[cfg(windows)]
impl JobObject {
    pub fn create() -> Result<Self, HostError> {
        use std::ffi::c_void;
        use windows_sys::Win32::System::JobObjects::{
            CreateJobObjectW, JobObjectExtendedLimitInformation, SetInformationJobObject,
            JOBOBJECT_EXTENDED_LIMIT_INFORMATION, JOB_OBJECT_LIMIT_BREAKAWAY_OK,
            JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE,
        };

        let handle = unsafe { CreateJobObjectW(std::ptr::null(), std::ptr::null()) };
        if handle as usize == 0 {
            return Err(HostError::bridge_unavailable());
        }
        let job = Self {
            handle: handle as usize,
        };

        let mut information: JOBOBJECT_EXTENDED_LIMIT_INFORMATION =
            unsafe { std::mem::zeroed() };
        information.BasicLimitInformation.LimitFlags =
            JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE | JOB_OBJECT_LIMIT_BREAKAWAY_OK;
        let configured = unsafe {
            SetInformationJobObject(
                job.raw(),
                JobObjectExtendedLimitInformation,
                &information as *const _ as *const c_void,
                std::mem::size_of::<JOBOBJECT_EXTENDED_LIMIT_INFORMATION>() as u32,
            )
        };
        if configured == 0 {
            return Err(HostError::bridge_unavailable());
        }
        Ok(job)
    }

    /// Attach the exact spawned child. The caller must not write the `start`
    /// handshake until this succeeds.
    pub fn assign(&self, child: &Child) -> Result<(), HostError> {
        use std::os::windows::io::AsRawHandle;
        use windows_sys::Win32::System::JobObjects::AssignProcessToJobObject;

        let process = child.as_raw_handle() as windows_sys::Win32::Foundation::HANDLE;
        let assigned = unsafe { AssignProcessToJobObject(self.raw(), process) };
        if assigned == 0 {
            Err(HostError::bridge_unavailable())
        } else {
            Ok(())
        }
    }

    /// Terminate only the processes still inside the owned job. Breakaway
    /// helpers are no longer in the job and are intentionally untouched.
    pub fn terminate(&self) {
        use windows_sys::Win32::System::JobObjects::TerminateJobObject;
        unsafe {
            TerminateJobObject(self.raw(), 1);
        }
    }

    fn raw(&self) -> windows_sys::Win32::Foundation::HANDLE {
        self.handle as windows_sys::Win32::Foundation::HANDLE
    }
}

#[cfg(windows)]
impl Drop for JobObject {
    fn drop(&mut self) {
        use windows_sys::Win32::Foundation::CloseHandle;
        unsafe {
            CloseHandle(self.raw());
        }
    }
}

/// Non-Windows experiment builds keep the same Backend shape. The first
/// supported target is Windows x64; Unix process-group ownership is not claimed
/// by this module.
#[cfg(not(windows))]
pub struct JobObject;

#[cfg(not(windows))]
impl JobObject {
    pub fn create() -> Result<Self, HostError> {
        Ok(Self)
    }

    pub fn assign(&self, _child: &Child) -> Result<(), HostError> {
        Ok(())
    }

    pub fn terminate(&self) {}
}
