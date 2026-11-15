#![cfg(windows)]

use operon_desktop_experimental::maintenance::{MaintenanceLease, StartupGuard};
use uuid::Uuid;

#[test]
fn maintenance_and_startup_gate_are_mutually_exclusive() {
    let installation = format!("gate-test-{}", Uuid::new_v4());

    let startup = StartupGuard::acquire(&installation).expect("host startup gate");
    assert!(
        MaintenanceLease::acquire(&installation).is_err(),
        "installer must not acquire the gate while host startup holds the mutex"
    );
    drop(startup);

    let lease = MaintenanceLease::acquire(&installation).expect("installer maintenance gate");
    assert!(
        StartupGuard::acquire(&installation).is_err(),
        "host startup must fail while the maintenance event is active"
    );
    drop(lease);

    let startup = StartupGuard::acquire(&installation).expect("gate is reusable after maintenance");
    drop(startup);
}

#[test]
fn different_installations_are_independent() {
    let first = format!("gate-a-{}", Uuid::new_v4());
    let second = format!("gate-b-{}", Uuid::new_v4());
    let _first = MaintenanceLease::acquire(&first).expect("first lease");
    let _second = MaintenanceLease::acquire(&second).expect("second lease");
}
