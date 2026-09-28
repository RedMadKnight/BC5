// SPDX-License-Identifier: GPL-2.0-only

#[test]
fn version_is_set() {
    assert!(!bc5_mount::VERSION.is_empty());
}
