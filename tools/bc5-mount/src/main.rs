// SPDX-License-Identifier: GPL-2.0-only

fn main() {
    if std::env::args().nth(1).as_deref() == Some("--version") {
        println!("bc5-mount {}", bc5_mount::VERSION);
        return;
    }
    eprintln!("bc5-mount: not implemented yet (phase 0a, see docs/PHASES.md)");
    std::process::exit(2);
}
