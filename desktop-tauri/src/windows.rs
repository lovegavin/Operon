//! Owned-process lifetime primitives.
//!
//! On Windows the management service is assigned to one Job Object created with
//! exactly the same limits as the existing C# host:
//! `KILL_ON_JOB_CLOSE | BREAKAWAY_OK`. Closing the job handle when the host
//! really dies terminates the owned service tree; a child that explicitly asks
//! to break away (the existing shared pool/viewer helpers) is allowed to leave
//! the job and survive. No process-name based cleanup is performed here.
//! Graceful shutdown additionally requires the job accounting count to reach
//! zero; a parent exit alone is not treated as a tree drain.

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

        let mut information: JOBOBJECT_EXTENDED_LIMIT_INFORMATION = unsafe { std::mem::zeroed() };
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
        use windows_sys::Win32::System::JobObjects::AssignProcessToJobObject;

        let process = child
            .raw_handle()
            .ok_or_else(HostError::bridge_unavailable)?
            as windows_sys::Win32::Foundation::HANDLE;
        let assigned = unsafe { AssignProcessToJobObject(self.raw(), process) };
        if assigned == 0 {
            Err(HostError::bridge_unavailable())
        } else {
            Ok(())
        }
    }

    /// Verify the announced server is in this exact owned job. CPython's
    /// Windows venv redirector can have a different PID from its real server.
    pub fn contains_pid(&self, pid: u32) -> Result<bool, HostError> {
        use windows_sys::Win32::{
            Foundation::CloseHandle,
            System::{
                JobObjects::IsProcessInJob,
                Threading::{GetProcessId, OpenProcess, PROCESS_QUERY_LIMITED_INFORMATION},
            },
        };
        let process = unsafe { OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, 0, pid) };
        if process.is_null() {
            return Ok(false);
        }
        // Some Windows handle APIs ignore low PID bits. Require the real ID,
        // not merely a successfully opened process handle.
        if unsafe { GetProcessId(process) } != pid {
            unsafe {
                CloseHandle(process);
            }
            return Ok(false);
        }
        let mut inside = 0;
        let result = unsafe { IsProcessInJob(process, self.raw(), &mut inside) };
        unsafe {
            CloseHandle(process);
        }
        if result == 0 {
            Err(HostError::bridge_unavailable())
        } else {
            Ok(inside != 0)
        }
    }

    /// The child was created suspended, so it cannot launch a redirector/helper
    /// before job assignment. Resume only its original, still-suspended thread.
    pub fn resume_child(&self, child: &Child) -> Result<(), HostError> {
        use windows_sys::Win32::{
            Foundation::{CloseHandle, INVALID_HANDLE_VALUE},
            System::{
                Diagnostics::ToolHelp::{
                    CreateToolhelp32Snapshot, Thread32First, Thread32Next, TH32CS_SNAPTHREAD,
                    THREADENTRY32,
                },
                Threading::{OpenThread, ResumeThread, THREAD_SUSPEND_RESUME},
            },
        };
        let pid = child.id().ok_or_else(HostError::bridge_unavailable)?;
        if !self.contains_pid(pid)? {
            return Err(HostError::bridge_unavailable());
        }
        let snapshot = unsafe { CreateToolhelp32Snapshot(TH32CS_SNAPTHREAD, 0) };
        if snapshot == INVALID_HANDLE_VALUE {
            return Err(HostError::bridge_unavailable());
        }
        let mut entry: THREADENTRY32 = unsafe { std::mem::zeroed() };
        entry.dwSize = std::mem::size_of::<THREADENTRY32>() as u32;
        let mut found = None;
        let mut more = unsafe { Thread32First(snapshot, &mut entry) };
        while more != 0 {
            if entry.th32OwnerProcessID == pid {
                found = Some(entry.th32ThreadID);
                break;
            }
            more = unsafe { Thread32Next(snapshot, &mut entry) };
        }
        unsafe {
            CloseHandle(snapshot);
        }
        let thread_id = found.ok_or_else(HostError::bridge_unavailable)?;
        let thread = unsafe { OpenThread(THREAD_SUSPEND_RESUME, 0, thread_id) };
        if thread.is_null() {
            return Err(HostError::bridge_unavailable());
        }
        let previous = unsafe { ResumeThread(thread) };
        unsafe {
            CloseHandle(thread);
        }
        if previous == 1 {
            Ok(())
        } else {
            Err(HostError::bridge_unavailable())
        }
    }

    /// Number of active processes still in the owned job. A parent exit alone
    /// is not a tree drain: non-breakaway helpers remain counted here.
    pub fn active_processes(&self) -> Result<u32, HostError> {
        use std::ffi::c_void;
        use windows_sys::Win32::System::JobObjects::{
            JobObjectBasicAccountingInformation, QueryInformationJobObject,
            JOBOBJECT_BASIC_ACCOUNTING_INFORMATION,
        };

        let mut information: JOBOBJECT_BASIC_ACCOUNTING_INFORMATION = unsafe { std::mem::zeroed() };
        let mut returned_length = 0u32;
        let queried = unsafe {
            QueryInformationJobObject(
                self.raw(),
                JobObjectBasicAccountingInformation,
                &mut information as *mut _ as *mut c_void,
                std::mem::size_of::<JOBOBJECT_BASIC_ACCOUNTING_INFORMATION>() as u32,
                &mut returned_length,
            )
        };
        if queried == 0 {
            Err(HostError::bridge_unavailable())
        } else {
            Ok(information.ActiveProcesses)
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

    pub fn contains_pid(&self, _pid: u32) -> Result<bool, HostError> {
        Err(HostError::unsupported(None))
    }

    pub fn resume_child(&self, _child: &Child) -> Result<(), HostError> {
        Err(HostError::unsupported(None))
    }

    /// No Unix job-tree accounting is implemented in this Windows-x64
    /// experiment. Report unsupported rather than a fake empty-tree proof.
    pub fn active_processes(&self) -> Result<u32, HostError> {
        Err(HostError::unsupported(None))
    }

    pub fn terminate(&self) {}
}
