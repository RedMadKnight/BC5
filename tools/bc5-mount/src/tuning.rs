// SPDX-License-Identifier: GPL-2.0-only
//! The mount's switches for exp 0381's re-read test, all off by default. Unset
//! or invalid values leave the kernel's and the mount's behaviour as it was.

/// Largest kernel readahead the mount may ask for, KiB (the kernel caps it too).
const MAX_READAHEAD_KIB: u32 = 1 << 16;

/// The FUSE settings of a mount.
#[derive(Debug, Default, Clone, Copy, PartialEq, Eq)]
pub struct Tuning {
    /// `BC5_MOUNT_MAX_READAHEAD_KIB`: the kernel's readahead on the mounted
    /// files, bytes; 0 asks for none.
    pub max_readahead: Option<u32>,
    /// `BC5_MOUNT_DIRECT_IO=1`: reads pass the kernel's page cache by, so the
    /// mount's block cache is the only copy above the disk.
    pub direct_io: bool,
}

impl Tuning {
    /// The switches from the environment.
    pub fn from_env() -> Self {
        Self::from_lookup(|k| std::env::var(k).ok())
    }

    fn from_lookup(get: impl Fn(&str) -> Option<String>) -> Self {
        Self {
            max_readahead: get("BC5_MOUNT_MAX_READAHEAD_KIB")
                .and_then(|v| v.trim().parse::<u32>().ok())
                .filter(|&k| k <= MAX_READAHEAD_KIB)
                .map(|k| k << 10),
            direct_io: get("BC5_MOUNT_DIRECT_IO").as_deref() == Some("1"),
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn with(pairs: &[(&str, &str)]) -> Tuning {
        let pairs: Vec<(String, String)> = pairs
            .iter()
            .map(|(k, v)| ((*k).to_owned(), (*v).to_owned()))
            .collect();
        Tuning::from_lookup(move |k| pairs.iter().find(|(n, _)| n == k).map(|(_, v)| v.clone()))
    }

    #[test]
    fn unset_is_off() {
        assert_eq!(with(&[]), Tuning::default());
    }

    #[test]
    fn values_are_read() {
        let t = with(&[
            ("BC5_MOUNT_MAX_READAHEAD_KIB", "0"),
            ("BC5_MOUNT_DIRECT_IO", "1"),
        ]);
        assert_eq!(t.max_readahead, Some(0));
        assert!(t.direct_io);
        assert_eq!(
            with(&[("BC5_MOUNT_MAX_READAHEAD_KIB", "32")]).max_readahead,
            Some(32 << 10)
        );
    }

    #[test]
    fn invalid_values_stay_off() {
        let t = with(&[
            ("BC5_MOUNT_MAX_READAHEAD_KIB", "big"),
            ("BC5_MOUNT_DIRECT_IO", "0"),
        ]);
        assert_eq!(t, Tuning::default());
        assert_eq!(
            with(&[("BC5_MOUNT_MAX_READAHEAD_KIB", "99999999")]).max_readahead,
            None
        );
    }
}
