//! Opening committed artifacts through the authenticated service.
//!
//! The renderer never supplies a native path. It supplies opaque run, artifact
//! and file IDs. This module resolves them through the owned service, validates
//! the returned metadata, downloads the exact bytes into a private cache,
//! verifies SHA-256 and size, and only then hands the verified path to the OS.
//!
//! Cache layout: `<profile>/viewer-cache/<artifact digest>/<file sha256>.<ext>`.
//! The original artifact file name is never used as a path component; only a
//! strict, explicit extension allowlist is taken from it.
//!
//! The transport and opener are injectable so tests can exercise the real cache
//! and verification pipeline with an in-memory HTTP response and without
//! launching an application.

use crate::error::{HostError, HostNextAction};
use serde::de::DeserializeOwned;
use serde::Deserialize;
use sha2::{Digest, Sha256};
use std::fs::{self, File, OpenOptions};
use std::io::{self, Read, Write};
use std::path::{Path, PathBuf};
use std::sync::atomic::{AtomicU64, Ordering};
use std::time::Duration;
use url::{Host, Url};

const CACHE_DIR: &str = "viewer-cache";
const MAX_ID_BYTES: usize = 128;
const MAX_FILE_NAME_BYTES: usize = 2048;
const MAX_MEDIA_TYPE_BYTES: usize = 255;
const MAX_CURSOR_BYTES: usize = 600;
const MAX_ENTRIES: usize = 4096;
const MAX_FILE_PAGES: usize = 4096;
const MAX_ARTIFACT_PAGES: usize = 64;
const MAX_METADATA_BODY: usize = 4 * 1024 * 1024;
const MAX_CHUNK_BYTES: usize = 8 * 1024 * 1024;
const MAX_TOKEN_BYTES: usize = 4096;
const MAX_EMPTY_CHUNKS: u32 = 16;
const CONNECT_TIMEOUT: Duration = Duration::from_secs(15);
const REQUEST_TIMEOUT: Duration = Duration::from_secs(600);

const SAFE_EXTENSIONS: &[&str] = &[
    // Inert images and documents.
    "png", "jpg", "jpeg", "gif", "webp", "bmp", "tif", "tiff", "pdf", "svg",
    // Tabular and plain scientific text.
    "csv", "tsv", "txt", "tab", "dat",
    // Structural and chemistry formats.
    "pdb", "ent", "cif", "mmcif", "mcif", "mol", "mol2", "sdf", "xyz",
    // Sequence and annotation formats.
    "fasta", "fa", "fna", "faa", "fas", "ffn", "frn", "gb", "gbk", "genbank", "embl",
    "gff", "gff3", "gtf", "bed", "bedgraph", "wig", "bigwig", "bw", "bigbed", "bb",
    "vcf", "bcf", "sam", "bam", "cram", "fastq", "fq",
    // Chromatin contact matrices and trees.
    "hic", "cool", "mcool", "nwk", "newick", "tree",
];

/// File metadata returned by the authenticated artifact file list.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ArtifactFile {
    pub file_id: String,
    pub name: String,
    pub size_bytes: u64,
    pub sha256: String,
    pub media_type: String,
}

/// One page of `/api/v1/plans/{run}/artifacts/{artifact}/files`.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct FilesPage {
    pub files: Vec<ArtifactFile>,
    pub next_cursor: String,
    pub has_more: bool,
    pub artifact_id: Option<String>,
}

/// Artifact identity needed for the cache directory.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ArtifactSummary {
    pub artifact_id: String,
    /// The service exposes the artifact manifest digest in its `sha256` field.
    pub sha256: String,
}

/// One page of `/api/v1/plans/{run}/artifacts`.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ArtifactsPage {
    pub artifacts: Vec<ArtifactSummary>,
    pub next_cursor: String,
    pub has_more: bool,
}

/// Transport failure with no server text or native path attached.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum TransportError {
    NotFound,
    Unavailable,
    Malformed,
    TooLarge,
}

/// A bounded byte stream for one authenticated artifact download.
#[allow(async_fn_in_trait)]
pub trait ArtifactDownload: Send {
    async fn next_chunk(&mut self) -> Result<Option<Vec<u8>>, TransportError>;
    fn content_length(&self) -> Option<u64>;
    fn etag(&self) -> Option<&str>;
    fn content_type(&self) -> Option<&str>;
}

/// Authenticated service transport. Implementations must not follow redirects
/// and must use finite timeouts.
#[allow(async_fn_in_trait)]
pub trait ArtifactTransport: Send + Sync {
    type Download: ArtifactDownload;

    async fn artifacts_page(
        &self,
        url: Url,
        token: &str,
    ) -> Result<ArtifactsPage, TransportError>;

    async fn files_page(&self, url: Url, token: &str) -> Result<FilesPage, TransportError>;

    async fn open_download(
        &self,
        url: Url,
        token: &str,
    ) -> Result<Self::Download, TransportError>;
}

/// OS association boundary. Production uses the native Windows shell; tests
/// use an injected recorder. No command line or arbitrary executable is used.
pub trait PathOpener: Send + Sync {
    fn open(&self, path: &Path) -> Result<(), ()>;
}

/// Open a committed artifact by opaque IDs.
///
/// `origin` must be the owned loopback HTTP(S) origin. `token` is the bearer
/// token for that service. No native path is accepted or returned.
pub async fn open_committed_artifact(
    origin: &Url,
    token: &str,
    profile: &Path,
    run_id: &str,
    artifact_id: &str,
    file_id: &str,
) -> Result<(), HostError> {
    let transport = ReqwestArtifactTransport::new()?;
    open_committed_artifact_with(
        origin,
        token,
        profile,
        run_id,
        artifact_id,
        file_id,
        &transport,
        &SystemOpener,
    )
    .await
}

/// Testable implementation with injected transport and opener.
pub async fn open_committed_artifact_with<T, O>(
    origin: &Url,
    token: &str,
    profile: &Path,
    run_id: &str,
    artifact_id: &str,
    file_id: &str,
    transport: &T,
    opener: &O,
) -> Result<(), HostError>
where
    T: ArtifactTransport,
    O: PathOpener,
{
    validate_origin(origin)?;
    validate_token(token)?;
    if !valid_identifier(run_id) || !valid_identifier(artifact_id) || !valid_file_id(file_id) {
        return Err(HostError::request_stale(None));
    }

    let artifact_digest =
        resolve_artifact_digest(transport, origin, token, run_id, artifact_id).await?;
    let file = resolve_file(transport, origin, token, run_id, artifact_id, file_id).await?;
    let extension = validate_file_metadata(&file)?;
    let (final_path, cache_dir) =
        cache_path(profile, &artifact_digest, &file.sha256, &extension)?;

    match fs::symlink_metadata(&final_path) {
        Ok(_) => {
            if verify_cached(&final_path, &file).is_ok() {
                return open_verified(opener, &final_path);
            }
            remove_cache_regular(&final_path)?;
        }
        Err(error) if error.kind() == io::ErrorKind::NotFound => {}
        Err(_) => return Err(bridge()),
    }

    let url = download_url(origin, run_id, artifact_id, file_id)?;
    let temporary = download_verified(transport, url, token, &file, &cache_dir).await?;
    install_temp(temporary, &final_path, &file)?;

    if verify_cached(&final_path, &file).is_err() {
        let _ = remove_cache_regular(&final_path);
        return Err(bridge());
    }
    open_verified(opener, &final_path)
}

struct SystemOpener;

impl PathOpener for SystemOpener {
    fn open(&self, path: &Path) -> Result<(), ()> {
        open_path_with_system(path)
    }
}

fn open_verified<O: PathOpener>(opener: &O, path: &Path) -> Result<(), HostError> {
    opener.open(path).map_err(|_| {
        HostError::capability_unavailable(HostNextAction::UseHttpArtifactLink, None)
    })
}

fn validate_origin(origin: &Url) -> Result<(), HostError> {
    if !matches!(origin.scheme(), "http" | "https") {
        return Err(HostError::unsupported(None));
    }
    if !origin.username().is_empty() || origin.password().is_some() {
        return Err(HostError::unsupported(None));
    }
    if origin.path() != "/" || origin.query().is_some() || origin.fragment().is_some() {
        return Err(HostError::unsupported(None));
    }
    let loopback = match origin.host() {
        Some(Host::Ipv4(address)) => address.is_loopback(),
        Some(Host::Ipv6(address)) => address.is_loopback(),
        Some(Host::Domain(host)) => host.eq_ignore_ascii_case("localhost"),
        None => false,
    };
    if !loopback {
        return Err(HostError::unsupported(None));
    }
    Ok(())
}

fn validate_token(token: &str) -> Result<(), HostError> {
    if token.is_empty()
        || token.len() > MAX_TOKEN_BYTES
        || !token.bytes().all(|byte| byte.is_ascii_graphic())
    {
        return Err(bridge());
    }
    Ok(())
}

fn valid_identifier(value: &str) -> bool {
    !value.is_empty()
        && value.len() <= MAX_ID_BYTES
        && value != "."
        && value != ".."
        && value
            .bytes()
            .all(|byte| byte.is_ascii_alphanumeric() || matches!(byte, b'_' | b'.' | b'-'))
}

fn valid_file_id(value: &str) -> bool {
    value.len() == 64
        && value
            .bytes()
            .all(|byte| matches!(byte, b'0'..=b'9' | b'a'..=b'f'))
}

fn valid_sha256(value: &str) -> bool {
    valid_file_id(value)
}

fn valid_cursor(value: &str) -> bool {
    value.len() <= MAX_CURSOR_BYTES
        && value.bytes().all(|byte| {
            byte.is_ascii_alphanumeric() || matches!(byte, b'_' | b'.' | b':' | b'/' | b'-')
        })
}

fn valid_media_type(value: &str) -> bool {
    !value.is_empty()
        && value.len() <= MAX_MEDIA_TYPE_BYTES
        && value
            .bytes()
            .all(|byte| byte.is_ascii_graphic() || byte == b' ')
}

fn validate_file_metadata(file: &ArtifactFile) -> Result<String, HostError> {
    if !valid_file_id(&file.file_id) || !valid_sha256(&file.sha256) {
        return Err(bridge());
    }
    if !valid_media_type(&file.media_type) {
        return Err(bridge());
    }
    validate_artifact_name(&file.name)
}

fn validate_artifact_name(name: &str) -> Result<String, HostError> {
    if name.is_empty() || name.len() > MAX_FILE_NAME_BYTES || name.chars().any(char::is_control)
    {
        return Err(bridge());
    }
    if name.starts_with('/') || name.contains('\\') || name.contains(':') {
        return Err(bridge());
    }
    for part in name.split('/') {
        if part.is_empty() || part == "." || part == ".." {
            return Err(bridge());
        }
    }
    let leaf = name.rsplit('/').next().unwrap_or("");
    let (_, extension) = leaf
        .rsplit_once('.')
        .ok_or_else(unsupported_extension)?;
    if extension.is_empty() || extension.len() > 16 {
        return Err(unsupported_extension());
    }
    let extension = extension.to_ascii_lowercase();
    if !SAFE_EXTENSIONS.contains(&extension.as_str()) {
        return Err(unsupported_extension());
    }
    Ok(extension)
}

fn unsupported_extension() -> HostError {
    HostError::capability_unavailable(HostNextAction::UseHttpArtifactLink, None)
}

fn artifacts_url(origin: &Url, run_id: &str, after: &str) -> Result<Url, HostError> {
    let mut url = origin
        .join(&format!("/api/v1/plans/{run_id}/artifacts"))
        .map_err(|_| bridge())?;
    url.query_pairs_mut()
        .append_pair("after", after)
        .append_pair("limit", "200")
        .append_pair("max_bytes", "65536");
    Ok(url)
}

fn files_url(
    origin: &Url,
    run_id: &str,
    artifact_id: &str,
    after: &str,
) -> Result<Url, HostError> {
    let mut url = origin
        .join(&format!(
            "/api/v1/plans/{run_id}/artifacts/{artifact_id}/files"
        ))
        .map_err(|_| bridge())?;
    url.query_pairs_mut()
        .append_pair("after", after)
        .append_pair("limit", "200")
        .append_pair("max_bytes", "65536");
    Ok(url)
}

fn download_url(
    origin: &Url,
    run_id: &str,
    artifact_id: &str,
    file_id: &str,
) -> Result<Url, HostError> {
    origin
        .join(&format!(
            "/api/v1/plans/{run_id}/artifacts/{artifact_id}/files/{file_id}/open"
        ))
        .map_err(|_| bridge())
}

async fn resolve_artifact_digest<T: ArtifactTransport>(
    transport: &T,
    origin: &Url,
    token: &str,
    run_id: &str,
    artifact_id: &str,
) -> Result<String, HostError> {
    let mut after = String::new();
    let mut pages = 0usize;
    loop {
        if pages >= MAX_ARTIFACT_PAGES {
            return Err(bridge());
        }
        pages += 1;
        let url = artifacts_url(origin, run_id, &after)?;
        let page = transport
            .artifacts_page(url, token)
            .await
            .map_err(map_transport)?;
        if page.artifacts.is_empty() && page.has_more {
            return Err(bridge());
        }
        for artifact in &page.artifacts {
            if !valid_identifier(&artifact.artifact_id) {
                return Err(bridge());
            }
            if artifact.artifact_id == artifact_id {
                if !valid_sha256(&artifact.sha256) {
                    return Err(bridge());
                }
                return Ok(artifact.sha256.clone());
            }
        }
        if !page.has_more {
            return Err(HostError::request_stale(None));
        }
        if page.next_cursor.is_empty()
            || !valid_cursor(&page.next_cursor)
            || page.next_cursor == after
        {
            return Err(bridge());
        }
        after = page.next_cursor;
    }
}

async fn resolve_file<T: ArtifactTransport>(
    transport: &T,
    origin: &Url,
    token: &str,
    run_id: &str,
    artifact_id: &str,
    file_id: &str,
) -> Result<ArtifactFile, HostError> {
    let mut after = String::new();
    let mut pages = 0usize;
    let mut entries = 0usize;
    loop {
        if pages >= MAX_FILE_PAGES {
            return Err(bridge());
        }
        pages += 1;
        let url = files_url(origin, run_id, artifact_id, &after)?;
        let page = transport
            .files_page(url, token)
            .await
            .map_err(map_transport)?;

        if let Some(page_artifact) = page.artifact_id.as_deref() {
            if page_artifact != artifact_id {
                return Err(bridge());
            }
        }
        if page.files.is_empty() && page.has_more {
            return Err(bridge());
        }
        for file in &page.files {
            if !valid_file_id(&file.file_id) {
                return Err(bridge());
            }
            entries += 1;
            if entries > MAX_ENTRIES {
                return Err(bridge());
            }
            if file.file_id == file_id {
                return Ok(file.clone());
            }
        }
        if !page.has_more {
            return Err(HostError::request_stale(None));
        }
        if page.next_cursor.is_empty()
            || !valid_cursor(&page.next_cursor)
            || page.next_cursor == after
        {
            return Err(bridge());
        }
        after = page.next_cursor;
    }
}

fn cache_path(
    profile: &Path,
    artifact_digest: &str,
    file_sha256: &str,
    extension: &str,
) -> Result<(PathBuf, PathBuf), HostError> {
    if !valid_sha256(artifact_digest)
        || !valid_sha256(file_sha256)
        || extension.is_empty()
        || !SAFE_EXTENSIONS.contains(&extension)
    {
        return Err(bridge());
    }

    let profile = fs::canonicalize(profile).map_err(|_| bridge())?;
    let profile_metadata = fs::metadata(&profile).map_err(|_| bridge())?;
    if !profile_metadata.is_dir() {
        return Err(bridge());
    }

    let cache_root = ensure_dir(&profile, CACHE_DIR)?;
    let artifact_dir = ensure_dir(&cache_root, artifact_digest)?;
    let final_path = artifact_dir.join(format!("{file_sha256}.{extension}"));
    Ok((final_path, artifact_dir))
}

fn ensure_dir(parent: &Path, name: &str) -> Result<PathBuf, HostError> {
    if name.is_empty()
        || name == "."
        || name == ".."
        || name.contains('/')
        || name.contains('\\')
        || name.contains(':')
    {
        return Err(bridge());
    }
    let path = parent.join(name);
    match fs::symlink_metadata(&path) {
        Ok(metadata) => {
            if !metadata.is_dir() {
                return Err(bridge());
            }
            reject_reparse_metadata(&metadata)?;
        }
        Err(error) if error.kind() == io::ErrorKind::NotFound => {
            fs::create_dir(&path).map_err(|_| bridge())?;
            set_private_dir(&path).map_err(|_| bridge())?;
            let metadata = fs::symlink_metadata(&path).map_err(|_| bridge())?;
            if !metadata.is_dir() {
                return Err(bridge());
            }
            reject_reparse_metadata(&metadata)?;
        }
        Err(_) => return Err(bridge()),
    }
    let canonical = fs::canonicalize(&path).map_err(|_| bridge())?;
    if !canonical.starts_with(parent) {
        return Err(bridge());
    }
    Ok(canonical)
}

fn verify_cached(path: &Path, expected: &ArtifactFile) -> Result<(), HostError> {
    let metadata = fs::symlink_metadata(path).map_err(|_| bridge())?;
    if !metadata.file_type().is_file() {
        return Err(bridge());
    }
    reject_reparse_metadata(&metadata)?;
    if metadata.len() != expected.size_bytes {
        return Err(bridge());
    }

    let mut file = File::open(path).map_err(|_| bridge())?;
    let mut hasher = Sha256::new();
    let mut buffer = vec![0u8; 1024 * 1024];
    let mut total = 0u64;
    loop {
        let read = file.read(&mut buffer).map_err(|_| bridge())?;
        if read == 0 {
            break;
        }
        total = total
            .checked_add(read as u64)
            .ok_or_else(bridge)?;
        if total > expected.size_bytes {
            return Err(bridge());
        }
        hasher.update(&buffer[..read]);
    }
    if total != expected.size_bytes || hex_lower(&hasher.finalize()) != expected.sha256 {
        return Err(bridge());
    }
    Ok(())
}

async fn download_verified<T: ArtifactTransport>(
    transport: &T,
    url: Url,
    token: &str,
    expected: &ArtifactFile,
    cache_dir: &Path,
) -> Result<TempGuard, HostError> {
    let mut download = transport
        .open_download(url, token)
        .await
        .map_err(map_transport)?;

    if let Some(length) = download.content_length() {
        if length != expected.size_bytes {
            return Err(bridge());
        }
    }
    if let Some(etag) = download.etag() {
        if etag.trim().trim_matches('"') != expected.sha256 {
            return Err(bridge());
        }
    }
    if let Some(content_type) = download.content_type() {
        let essence = content_type.split(';').next().unwrap_or("").trim();
        if !essence.eq_ignore_ascii_case(&expected.media_type) {
            return Err(bridge());
        }
    }

    let (temporary, mut file) = create_temp(cache_dir)?;
    let mut hasher = Sha256::new();
    let mut written = 0u64;
    let mut empty_chunks = 0u32;
    loop {
        let chunk = download
            .next_chunk()
            .await
            .map_err(map_transport)?;
        let Some(chunk) = chunk else {
            break;
        };
        if chunk.is_empty() {
            empty_chunks += 1;
            if empty_chunks > MAX_EMPTY_CHUNKS {
                return Err(bridge());
            }
            continue;
        }
        if chunk.len() > MAX_CHUNK_BYTES {
            return Err(bridge());
        }
        written = written
            .checked_add(chunk.len() as u64)
            .ok_or_else(bridge)?;
        if written > expected.size_bytes {
            return Err(bridge());
        }
        file.write_all(&chunk).map_err(|_| bridge())?;
        hasher.update(&chunk);
    }
    if written != expected.size_bytes || hex_lower(&hasher.finalize()) != expected.sha256 {
        return Err(bridge());
    }
    file.sync_all().map_err(|_| bridge())?;
    drop(file);
    Ok(temporary)
}

fn create_temp(cache_dir: &Path) -> Result<(TempGuard, File), HostError> {
    static COUNTER: AtomicU64 = AtomicU64::new(0);
    for _ in 0..16 {
        let sequence = COUNTER.fetch_add(1, Ordering::Relaxed);
        let path = cache_dir.join(format!(
            ".operon-{}-{sequence}.tmp",
            std::process::id()
        ));
        let mut options = OpenOptions::new();
        options.write(true).create_new(true);
        #[cfg(unix)]
        {
            use std::os::unix::fs::OpenOptionsExt;
            options.mode(0o600);
        }
        match options.open(&path) {
            Ok(file) => return Ok((TempGuard::new(path), file)),
            Err(error) if error.kind() == io::ErrorKind::AlreadyExists => continue,
            Err(_) => return Err(bridge()),
        }
    }
    Err(bridge())
}

fn install_temp(
    mut temporary: TempGuard,
    final_path: &Path,
    expected: &ArtifactFile,
) -> Result<(), HostError> {
    for _ in 0..2 {
        match fs::rename(temporary.path(), final_path) {
            Ok(()) => {
                temporary.disarm();
                return Ok(());
            }
            Err(_) => {
                if !final_path.exists() {
                    return Err(bridge());
                }
                if verify_cached(final_path, expected).is_ok() {
                    // The concurrent writer produced the same verified bytes.
                    return Ok(());
                }
                remove_cache_regular(final_path)?;
            }
        }
    }
    Err(bridge())
}

fn remove_cache_regular(path: &Path) -> Result<(), HostError> {
    match fs::symlink_metadata(path) {
        Ok(metadata) => {
            if !metadata.file_type().is_file() {
                return Err(bridge());
            }
            reject_reparse_metadata(&metadata)?;
            fs::remove_file(path).map_err(|_| bridge())
        }
        Err(error) if error.kind() == io::ErrorKind::NotFound => Ok(()),
        Err(_) => Err(bridge()),
    }
}

fn reject_reparse_metadata(metadata: &fs::Metadata) -> Result<(), HostError> {
    if metadata.file_type().is_symlink() {
        return Err(bridge());
    }
    #[cfg(windows)]
    {
        use std::os::windows::fs::MetadataExt;
        const FILE_ATTRIBUTE_REPARSE_POINT: u32 = 0x0400;
        if metadata.file_attributes() & FILE_ATTRIBUTE_REPARSE_POINT != 0 {
            return Err(bridge());
        }
    }
    Ok(())
}

#[cfg(unix)]
fn set_private_dir(path: &Path) -> io::Result<()> {
    use std::os::unix::fs::PermissionsExt;
    fs::set_permissions(path, fs::Permissions::from_mode(0o700))
}

#[cfg(not(unix))]
fn set_private_dir(_path: &Path) -> io::Result<()> {
    // The profile's existing ACL is the privacy boundary on Windows. No ACL
    // changes are attempted by this module.
    Ok(())
}

struct TempGuard {
    path: PathBuf,
    armed: bool,
}

impl TempGuard {
    fn new(path: PathBuf) -> Self {
        Self { path, armed: true }
    }

    fn path(&self) -> &Path {
        &self.path
    }

    fn disarm(&mut self) {
        self.armed = false;
    }
}

impl Drop for TempGuard {
    fn drop(&mut self) {
        if self.armed {
            let _ = fs::remove_file(&self.path);
        }
    }
}

fn bridge() -> HostError {
    HostError::bridge_unavailable()
}

fn map_transport(error: TransportError) -> HostError {
    match error {
        TransportError::NotFound => HostError::request_stale(None),
        TransportError::Unavailable | TransportError::Malformed | TransportError::TooLarge => {
            bridge()
        }
    }
}

fn hex_lower(bytes: &[u8]) -> String {
    const HEX: &[u8; 16] = b"0123456789abcdef";
    let mut output = String::with_capacity(bytes.len() * 2);
    for byte in bytes {
        output.push(HEX[(byte >> 4) as usize] as char);
        output.push(HEX[(byte & 0x0f) as usize] as char);
    }
    output
}

// ---- HTTP transport -------------------------------------------------------

/// `reqwest` transport with redirects disabled, proxies disabled and finite
/// timeouts. The bearer token is sent only to the validated service origin.
pub struct ReqwestArtifactTransport {
    client: reqwest::Client,
}

impl ReqwestArtifactTransport {
    pub fn new() -> Result<Self, HostError> {
        let client = reqwest::Client::builder()
            .redirect(reqwest::redirect::Policy::none())
            .no_proxy()
            .connect_timeout(CONNECT_TIMEOUT)
            .timeout(REQUEST_TIMEOUT)
            .build()
            .map_err(|_| bridge())?;
        Ok(Self { client })
    }

    async fn send(&self, url: Url, token: &str) -> Result<reqwest::Response, TransportError> {
        let response = self
            .client
            .get(url)
            .bearer_auth(token)
            .header(reqwest::header::ACCEPT_ENCODING, "identity")
            .send()
            .await
            .map_err(|_| TransportError::Unavailable)?;
        if response.status() == reqwest::StatusCode::NOT_FOUND {
            return Err(TransportError::NotFound);
        }
        if !response.status().is_success() {
            return Err(TransportError::Unavailable);
        }
        Ok(response)
    }

    async fn get_json<T: DeserializeOwned>(
        &self,
        url: Url,
        token: &str,
    ) -> Result<T, TransportError> {
        let mut response = self.send(url, token).await?;
        if let Some(length) = response.content_length() {
            if length > MAX_METADATA_BODY as u64 {
                return Err(TransportError::TooLarge);
            }
        }
        let mut body = Vec::new();
        while let Some(chunk) = response
            .chunk()
            .await
            .map_err(|_| TransportError::Unavailable)?
        {
            if chunk.len() > MAX_METADATA_BODY
                || body
                    .len()
                    .checked_add(chunk.len())
                    .map_or(true, |total| total > MAX_METADATA_BODY)
            {
                return Err(TransportError::TooLarge);
            }
            body.extend_from_slice(chunk.as_ref());
        }
        serde_json::from_slice(&body).map_err(|_| TransportError::Malformed)
    }
}

impl ArtifactTransport for ReqwestArtifactTransport {
    type Download = ReqwestDownload;

    async fn artifacts_page(
        &self,
        url: Url,
        token: &str,
    ) -> Result<ArtifactsPage, TransportError> {
        let raw: RawArtifactsPage = self.get_json(url, token).await?;
        Ok(ArtifactsPage {
            artifacts: raw
                .artifacts
                .into_iter()
                .map(|artifact| ArtifactSummary {
                    artifact_id: artifact.artifact_id,
                    sha256: artifact.sha256,
                })
                .collect(),
            next_cursor: raw.next_cursor,
            has_more: raw.has_more,
        })
    }

    async fn files_page(&self, url: Url, token: &str) -> Result<FilesPage, TransportError> {
        let raw: RawFilesPage = self.get_json(url, token).await?;
        Ok(FilesPage {
            files: raw
                .files
                .into_iter()
                .map(|file| ArtifactFile {
                    file_id: file.file_id,
                    name: file.name,
                    size_bytes: file.size_bytes,
                    sha256: file.sha256,
                    media_type: file.media_type,
                })
                .collect(),
            next_cursor: raw.next_cursor,
            has_more: raw.has_more,
            artifact_id: raw.artifact_id,
        })
    }

    async fn open_download(
        &self,
        url: Url,
        token: &str,
    ) -> Result<Self::Download, TransportError> {
        Ok(ReqwestDownload {
            response: self.send(url, token).await?,
        })
    }
}

pub struct ReqwestDownload {
    response: reqwest::Response,
}

impl ReqwestDownload {
    fn header(&self, name: &'static str) -> Option<&str> {
        self.response
            .headers()
            .get(name)
            .and_then(|value| value.to_str().ok())
    }
}

impl ArtifactDownload for ReqwestDownload {
    async fn next_chunk(&mut self) -> Result<Option<Vec<u8>>, TransportError> {
        self.response
            .chunk()
            .await
            .map(|chunk| chunk.map(|bytes| bytes.to_vec()))
            .map_err(|_| TransportError::Unavailable)
    }

    fn content_length(&self) -> Option<u64> {
        self.response.content_length()
    }

    fn etag(&self) -> Option<&str> {
        self.header("etag")
    }

    fn content_type(&self) -> Option<&str> {
        self.header("content-type")
    }
}

#[derive(Deserialize)]
struct RawArtifactsPage {
    artifacts: Vec<RawArtifact>,
    next_cursor: String,
    has_more: bool,
}

#[derive(Deserialize)]
struct RawArtifact {
    artifact_id: String,
    sha256: String,
}

#[derive(Deserialize)]
struct RawFilesPage {
    files: Vec<RawFile>,
    next_cursor: String,
    has_more: bool,
    #[serde(default)]
    artifact_id: Option<String>,
}

#[derive(Deserialize)]
struct RawFile {
    file_id: String,
    name: String,
    size_bytes: u64,
    sha256: String,
    media_type: String,
}

// ---- Native opener --------------------------------------------------------

#[cfg(windows)]
fn open_path_with_system(path: &Path) -> Result<(), ()> {
    use windows_sys::Win32::UI::Shell::ShellExecuteW;

    let operation: Vec<u16> = "open\0".encode_utf16().collect();
    // Rust canonicalization yields a verbatim `\\?\` path. ShellExecuteW is
    // more reliable with the ordinary Win32 form; the cache path is already
    // canonical and ASCII for its owned components.
    let mut text = path.to_string_lossy().into_owned();
    let stripped = if let Some(rest) = text.strip_prefix(r"\\?\UNC\") {
        Some(format!(r"\\{rest}"))
    } else {
        text.strip_prefix(r"\\?\").map(|rest| rest.to_owned())
    };
    if let Some(stripped) = stripped {
        text = stripped;
    }
    let target: Vec<u16> = text.encode_utf16().chain(std::iter::once(0)).collect();
    let hwnd: windows_sys::Win32::Foundation::HWND = unsafe { std::mem::zeroed() };
    let result = unsafe {
        ShellExecuteW(
            hwnd,
            operation.as_ptr(),
            target.as_ptr(),
            std::ptr::null(),
            std::ptr::null(),
            1, // SW_SHOWNORMAL
        )
    };
    if result as isize > 32 {
        Ok(())
    } else {
        Err(())
    }
}

#[cfg(not(windows))]
fn open_path_with_system(_path: &Path) -> Result<(), ()> {
    // Windows x64 is the first supported experiment. Never fall back to a shell
    // command or an arbitrary executable on another platform.
    Err(())
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::collections::VecDeque;
    use std::sync::atomic::AtomicUsize;
    use std::sync::Mutex;

    fn origin() -> Url {
        Url::parse("http://127.0.0.1:43210/").unwrap()
    }

    fn sha(content: &[u8]) -> String {
        hex_lower(&Sha256::digest(content))
    }

    fn artifact_page(digest: &str) -> ArtifactsPage {
        ArtifactsPage {
            artifacts: vec![ArtifactSummary {
                artifact_id: "art-1".to_owned(),
                sha256: digest.to_owned(),
            }],
            next_cursor: String::new(),
            has_more: false,
        }
    }

    fn files_page(file: ArtifactFile) -> FilesPage {
        FilesPage {
            files: vec![file],
            next_cursor: String::new(),
            has_more: false,
            artifact_id: Some("art-1".to_owned()),
        }
    }

    fn metadata(name: &str, content: &[u8]) -> ArtifactFile {
        ArtifactFile {
            file_id: "b".repeat(64),
            name: name.to_owned(),
            size_bytes: content.len() as u64,
            sha256: sha(content),
            media_type: "image/png".to_owned(),
        }
    }

    #[derive(Clone)]
    struct MockDownloadSpec {
        chunks: Vec<Vec<u8>>,
        content_length: Option<u64>,
        etag: Option<String>,
        content_type: Option<String>,
    }

    struct MockTransport {
        artifact_pages: Mutex<VecDeque<ArtifactsPage>>,
        file_pages: Mutex<VecDeque<FilesPage>>,
        downloads: Mutex<VecDeque<MockDownloadSpec>>,
        download_count: AtomicUsize,
        artifact_urls: Mutex<Vec<String>>,
        file_urls: Mutex<Vec<String>>,
    }

    impl Default for MockTransport {
        fn default() -> Self {
            Self {
                artifact_pages: Mutex::new(VecDeque::new()),
                file_pages: Mutex::new(VecDeque::new()),
                downloads: Mutex::new(VecDeque::new()),
                download_count: AtomicUsize::new(0),
                artifact_urls: Mutex::new(Vec::new()),
                file_urls: Mutex::new(Vec::new()),
            }
        }
    }

    impl MockTransport {
        fn with_pages(
            artifact_pages: Vec<ArtifactsPage>,
            file_pages: Vec<FilesPage>,
            download: MockDownloadSpec,
        ) -> Self {
            Self {
                artifact_pages: Mutex::new(artifact_pages.into()),
                file_pages: Mutex::new(file_pages.into()),
                downloads: Mutex::new(vec![download].into()),
                download_count: AtomicUsize::new(0),
                artifact_urls: Mutex::new(Vec::new()),
                file_urls: Mutex::new(Vec::new()),
            }
        }

        fn downloads(&self) -> usize {
            self.download_count.load(Ordering::SeqCst)
        }
    }

    struct MockDownload {
        chunks: VecDeque<Vec<u8>>,
        content_length: Option<u64>,
        etag: Option<String>,
        content_type: Option<String>,
    }

    impl ArtifactDownload for MockDownload {
        async fn next_chunk(&mut self) -> Result<Option<Vec<u8>>, TransportError> {
            Ok(self.chunks.pop_front())
        }

        fn content_length(&self) -> Option<u64> {
            self.content_length
        }

        fn etag(&self) -> Option<&str> {
            self.etag.as_deref()
        }

        fn content_type(&self) -> Option<&str> {
            self.content_type.as_deref()
        }
    }

    impl ArtifactTransport for MockTransport {
        type Download = MockDownload;

        async fn artifacts_page(
            &self,
            url: Url,
            _token: &str,
        ) -> Result<ArtifactsPage, TransportError> {
            self.artifact_urls.lock().unwrap().push(url.to_string());
            self.artifact_pages
                .lock()
                .unwrap()
                .pop_front()
                .ok_or(TransportError::Unavailable)
        }

        async fn files_page(&self, url: Url, _token: &str) -> Result<FilesPage, TransportError> {
            self.file_urls.lock().unwrap().push(url.to_string());
            self.file_pages
                .lock()
                .unwrap()
                .pop_front()
                .ok_or(TransportError::Unavailable)
        }

        async fn open_download(
            &self,
            _url: Url,
            _token: &str,
        ) -> Result<Self::Download, TransportError> {
            self.download_count.fetch_add(1, Ordering::SeqCst);
            let spec = self
                .downloads
                .lock()
                .unwrap()
                .pop_front()
                .ok_or(TransportError::Unavailable)?;
            Ok(MockDownload {
                chunks: spec.chunks.into(),
                content_length: spec.content_length,
                etag: spec.etag,
                content_type: spec.content_type,
            })
        }
    }

    #[derive(Default)]
    struct MockOpener {
        opened: Mutex<Vec<PathBuf>>,
    }

    impl PathOpener for MockOpener {
        fn open(&self, path: &Path) -> Result<(), ()> {
            self.opened.lock().unwrap().push(path.to_path_buf());
            Ok(())
        }
    }

    fn download(metadata: &ArtifactFile, content: &[u8]) -> MockDownloadSpec {
        MockDownloadSpec {
            chunks: vec![content.to_vec()],
            content_length: Some(metadata.size_bytes),
            etag: Some(format!("\"{}\"", metadata.sha256)),
            content_type: Some(metadata.media_type.clone()),
        }
    }

    #[test]
    fn artifact_origin_must_be_a_bare_loopback_http_origin() {
        assert!(validate_origin(&origin()).is_ok());
        assert!(validate_origin(&Url::parse("http://localhost:1234/").unwrap()).is_ok());
        for rejected in [
            "https://evil.example/",
            "http://127.0.0.1:1234/path",
            "http://127.0.0.1:1234/?x=1",
            "http://user@127.0.0.1:1234/",
            "file:///C:/Windows/",
            "javascript:alert(1)",
        ] {
            assert!(
                validate_origin(&Url::parse(rejected).unwrap()).is_err(),
                "must reject {rejected}"
            );
        }
    }

    #[test]
    fn artifact_token_is_bounded_and_printable() {
        assert!(validate_token("token-value_123").is_ok());
        for rejected in ["", "with space", "with\nnewline", "é"] {
            assert!(validate_token(rejected).is_err(), "must reject token");
        }
        assert!(validate_token(&"x".repeat(MAX_TOKEN_BYTES + 1)).is_err());
    }

    #[tokio::test]
    async fn downloads_verifies_and_opens_verified_path() {
        let directory = tempfile::tempdir().unwrap();
        let content = b"\x89PNG\r\n\x1a\n";
        let file = metadata("plot.png", content);
        let digest = "a".repeat(64);
        let transport = MockTransport::with_pages(
            vec![artifact_page(&digest)],
            vec![files_page(file.clone())],
            download(&file, content),
        );
        let opener = MockOpener::default();

        open_committed_artifact_with(
            &origin(),
            "token",
            directory.path(),
            "run-1",
            "art-1",
            &file.file_id,
            &transport,
            &opener,
        )
        .await
        .unwrap();

        let opened = opener.opened.lock().unwrap();
        assert_eq!(opened.len(), 1);
        let path = &opened[0];
        assert_eq!(fs::read(path).unwrap(), content.to_vec());
        assert_eq!(
            path.extension().and_then(|extension| extension.to_str()),
            Some("png")
        );
        let expected_name = format!("{}.png", file.sha256);
        assert_eq!(
            path.file_name().and_then(|name| name.to_str()),
            Some(expected_name.as_str())
        );
        let expected_parent = fs::canonicalize(directory.path())
            .unwrap()
            .join("viewer-cache")
            .join(&digest);
        assert_eq!(path.parent(), Some(expected_parent.as_path()));
        assert_eq!(transport.downloads(), 1);
        assert_eq!(
            transport.artifact_urls.lock().unwrap()[0].as_str(),
            "http://127.0.0.1:43210/api/v1/plans/run-1/artifacts?after=&limit=200&max_bytes=65536"
        );
    }

    #[tokio::test]
    async fn reuses_and_rehashes_existing_cache() {
        let directory = tempfile::tempdir().unwrap();
        let content = b"cached bytes";
        let file = metadata("plot.png", content);
        let digest = "a".repeat(64);
        let transport = MockTransport::with_pages(
            vec![artifact_page(&digest), artifact_page(&digest)],
            vec![files_page(file.clone()), files_page(file.clone())],
            download(&file, content),
        );
        let opener = MockOpener::default();

        open_committed_artifact_with(
            &origin(),
            "token",
            directory.path(),
            "run-1",
            "art-1",
            &file.file_id,
            &transport,
            &opener,
        )
        .await
        .unwrap();
        assert_eq!(transport.downloads(), 1);

        // No download spec is left; success proves the cached file was reused.
        open_committed_artifact_with(
            &origin(),
            "token",
            directory.path(),
            "run-1",
            "art-1",
            &file.file_id,
            &transport,
            &opener,
        )
        .await
        .unwrap();
        assert_eq!(transport.downloads(), 1);
        assert_eq!(opener.opened.lock().unwrap().len(), 2);
    }

    #[tokio::test]
    async fn corrupt_cache_is_replaced() {
        let directory = tempfile::tempdir().unwrap();
        let content = b"correct bytes";
        let file = metadata("plot.png", content);
        let digest = "a".repeat(64);
        let first = MockTransport::with_pages(
            vec![artifact_page(&digest)],
            vec![files_page(file.clone())],
            download(&file, content),
        );
        let opener = MockOpener::default();

        open_committed_artifact_with(
            &origin(),
            "token",
            directory.path(),
            "run-1",
            "art-1",
            &file.file_id,
            &first,
            &opener,
        )
        .await
        .unwrap();
        let path = opener.opened.lock().unwrap()[0].clone();
        fs::write(&path, b"corrupt bytes").unwrap();

        let second = MockTransport::with_pages(
            vec![artifact_page(&digest)],
            vec![files_page(file.clone())],
            download(&file, content),
        );
        open_committed_artifact_with(
            &origin(),
            "token",
            directory.path(),
            "run-1",
            "art-1",
            &file.file_id,
            &second,
            &opener,
        )
        .await
        .unwrap();
        assert_eq!(second.downloads(), 1);
        assert_eq!(fs::read(&path).unwrap(), content.to_vec());
    }

    #[tokio::test]
    async fn rejects_invalid_opaque_ids_before_network() {
        let directory = tempfile::tempdir().unwrap();
        let transport = MockTransport::default();
        let opener = MockOpener::default();
        let valid_file = "b".repeat(64);
        let upper_file = "B".repeat(64);
        for (run, artifact, file) in [
            ("../run", "art-1", valid_file.as_str()),
            ("run-1", "../artifact", valid_file.as_str()),
            ("run-1", "art-1", upper_file.as_str()),
            ("run-1", "art-1", "short"),
        ] {
            let error = open_committed_artifact_with(
                &origin(),
                "token",
                directory.path(),
                run,
                artifact,
                file,
                &transport,
                &opener,
            )
            .await
            .unwrap_err();
            assert_eq!(error.code(), crate::error::HostErrorCode::HostRequestStale);
        }
        assert!(transport.artifact_urls.lock().unwrap().is_empty());
        assert!(opener.opened.lock().unwrap().is_empty());
    }

    #[tokio::test]
    async fn unknown_file_reference_fails_without_opening() {
        let directory = tempfile::tempdir().unwrap();
        let content = b"bytes";
        let mut other = metadata("other.png", content);
        other.file_id = "c".repeat(64);
        let transport = MockTransport::with_pages(
            vec![artifact_page(&"a".repeat(64))],
            vec![files_page(other)],
            MockDownloadSpec {
                chunks: Vec::new(),
                content_length: None,
                etag: None,
                content_type: None,
            },
        );
        let opener = MockOpener::default();
        let missing_file = "b".repeat(64);

        let error = open_committed_artifact_with(
            &origin(),
            "token",
            directory.path(),
            "run-1",
            "art-1",
            &missing_file,
            &transport,
            &opener,
        )
        .await
        .unwrap_err();
        assert_eq!(error.code(), crate::error::HostErrorCode::HostRequestStale);
        assert!(opener.opened.lock().unwrap().is_empty());
        assert_eq!(transport.downloads(), 0);
    }

    #[tokio::test]
    async fn unsafe_extension_is_not_downloaded_or_opened() {
        let directory = tempfile::tempdir().unwrap();
        let content = b"MZ";
        let file = metadata("payload.exe", content);
        let transport = MockTransport::with_pages(
            vec![artifact_page(&"a".repeat(64))],
            vec![files_page(file.clone())],
            download(&file, content),
        );
        let opener = MockOpener::default();

        let error = open_committed_artifact_with(
            &origin(),
            "token",
            directory.path(),
            "run-1",
            "art-1",
            &file.file_id,
            &transport,
            &opener,
        )
        .await
        .unwrap_err();
        assert_eq!(
            error.code(),
            crate::error::HostErrorCode::HostCapabilityUnavailable
        );
        assert_eq!(error.next_actions().len(), 1);
        assert_eq!(
            error.next_actions()[0],
            HostNextAction::UseHttpArtifactLink
        );
        assert!(opener.opened.lock().unwrap().is_empty());
        assert_eq!(transport.downloads(), 0);
    }

    #[tokio::test]
    async fn traversal_in_server_file_name_is_rejected() {
        let directory = tempfile::tempdir().unwrap();
        let content = b"data";
        let file = metadata("../plot.png", content);
        let transport = MockTransport::with_pages(
            vec![artifact_page(&"a".repeat(64))],
            vec![files_page(file.clone())],
            download(&file, content),
        );
        let opener = MockOpener::default();

        let error = open_committed_artifact_with(
            &origin(),
            "token",
            directory.path(),
            "run-1",
            "art-1",
            &file.file_id,
            &transport,
            &opener,
        )
        .await
        .unwrap_err();
        assert_eq!(
            error.code(),
            crate::error::HostErrorCode::HostBridgeUnavailable
        );
        assert!(opener.opened.lock().unwrap().is_empty());
    }

    #[tokio::test]
    async fn sha_mismatch_leaves_no_cache_entry_or_open() {
        let directory = tempfile::tempdir().unwrap();
        let expected_content = b"expected";
        let actual_content = b"tampered";
        let file = metadata("plot.png", expected_content);
        let transport = MockTransport::with_pages(
            vec![artifact_page(&"a".repeat(64))],
            vec![files_page(file.clone())],
            download(&file, actual_content),
        );
        let opener = MockOpener::default();

        let error = open_committed_artifact_with(
            &origin(),
            "token",
            directory.path(),
            "run-1",
            "art-1",
            &file.file_id,
            &transport,
            &opener,
        )
        .await
        .unwrap_err();
        assert_eq!(
            error.code(),
            crate::error::HostErrorCode::HostBridgeUnavailable
        );
        assert!(opener.opened.lock().unwrap().is_empty());
        let cache = directory.path().join("viewer-cache");
        let entries = fs::read_dir(cache)
            .unwrap()
            .flat_map(|entry| fs::read_dir(entry.unwrap().path()).unwrap())
            .count();
        assert_eq!(entries, 0);
    }

    #[tokio::test]
    async fn wrong_length_or_etag_is_rejected() {
        let directory = tempfile::tempdir().unwrap();
        let content = b"bytes";
        let file = metadata("plot.png", content);

        let mut bad_length = download(&file, content);
        bad_length.content_length = Some(file.size_bytes + 1);
        let transport = MockTransport::with_pages(
            vec![artifact_page(&"a".repeat(64))],
            vec![files_page(file.clone())],
            bad_length,
        );
        let opener = MockOpener::default();
        assert!(open_committed_artifact_with(
            &origin(),
            "token",
            directory.path(),
            "run-1",
            "art-1",
            &file.file_id,
            &transport,
            &opener,
        )
        .await
        .is_err());
        assert!(opener.opened.lock().unwrap().is_empty());

        let mut bad_etag = download(&file, content);
        bad_etag.etag = Some("\"deadbeef\"".to_owned());
        let transport = MockTransport::with_pages(
            vec![artifact_page(&"a".repeat(64))],
            vec![files_page(file.clone())],
            bad_etag,
        );
        assert!(open_committed_artifact_with(
            &origin(),
            "token",
            directory.path(),
            "run-1",
            "art-1",
            &file.file_id,
            &transport,
            &opener,
        )
        .await
        .is_err());
        assert!(opener.opened.lock().unwrap().is_empty());
    }

    #[tokio::test]
    async fn follows_bounded_file_pagination() {
        let directory = tempfile::tempdir().unwrap();
        let content = b"paged bytes";
        let target = metadata("plot.png", content);
        let mut first = metadata("other.png", b"x");
        first.file_id = "c".repeat(64);
        let first_page = FilesPage {
            files: vec![first],
            next_cursor: "c".repeat(64),
            has_more: true,
            artifact_id: Some("art-1".to_owned()),
        };
        let second_page = FilesPage {
            files: vec![target.clone()],
            next_cursor: String::new(),
            has_more: false,
            artifact_id: Some("art-1".to_owned()),
        };
        let transport = MockTransport::with_pages(
            vec![artifact_page(&"a".repeat(64))],
            vec![first_page, second_page],
            download(&target, content),
        );
        let opener = MockOpener::default();

        open_committed_artifact_with(
            &origin(),
            "token",
            directory.path(),
            "run-1",
            "art-1",
            &target.file_id,
            &transport,
            &opener,
        )
        .await
        .unwrap();
        assert_eq!(transport.file_urls.lock().unwrap().len(), 2);
        assert!(transport.file_urls.lock().unwrap()[1].contains("after=cccc"));
    }

    #[tokio::test]
    async fn more_than_maximum_entries_is_rejected() {
        let directory = tempfile::tempdir().unwrap();
        let mut pages = Vec::new();
        for page_index in 0..21 {
            let files = (0..200)
                .map(|offset| {
                    let index = page_index * 200 + offset;
                    ArtifactFile {
                        file_id: format!("{index:064x}"),
                        name: "unused.txt".to_owned(),
                        size_bytes: 0,
                        sha256: "0".repeat(64),
                        media_type: "text/plain".to_owned(),
                    }
                })
                .collect();
            pages.push(FilesPage {
                files,
                next_cursor: format!("{:064x}", page_index * 200 + 199),
                has_more: true,
                artifact_id: Some("art-1".to_owned()),
            });
        }
        let transport = MockTransport::with_pages(
            vec![artifact_page(&"a".repeat(64))],
            pages,
            MockDownloadSpec {
                chunks: Vec::new(),
                content_length: None,
                etag: None,
                content_type: None,
            },
        );
        let opener = MockOpener::default();
        let missing_file = "f".repeat(64);

        let error = open_committed_artifact_with(
            &origin(),
            "token",
            directory.path(),
            "run-1",
            "art-1",
            &missing_file,
            &transport,
            &opener,
        )
        .await
        .unwrap_err();
        assert_eq!(
            error.code(),
            crate::error::HostErrorCode::HostBridgeUnavailable
        );
        assert!(opener.opened.lock().unwrap().is_empty());
    }

    #[test]
    fn extension_allowlist_is_explicit() {
        for accepted in [
            "plot.png",
            "plot.PDF",
            "plot.svg",
            "table.csv",
            "table.tsv",
            "readme.txt",
            "model.pdb",
            "model.cif",
            "seq.fasta",
            "matrix.hic",
            "matrix.cool",
            "matrix.mcool",
            "peaks.bed",
            "signal.bigwig",
            "record.genbank",
        ] {
            assert!(
                validate_artifact_name(accepted).is_ok(),
                "must accept {accepted}"
            );
        }
        for rejected in [
            "payload.exe",
            "payload.bat",
            "payload.cmd",
            "payload.ps1",
            "payload.js",
            "payload.html",
            "payload.htm",
            "payload.url",
            "payload.lnk",
            "payload.py",
            "payload.sh",
            "../../plot.png",
            "/absolute.png",
            r"C:\absolute.png",
            "dir//plot.png",
            "no-extension",
            "trailing.png.",
        ] {
            assert!(
                validate_artifact_name(rejected).is_err(),
                "must reject {rejected}"
            );
        }
    }

    #[cfg(unix)]
    #[tokio::test]
    async fn rejects_symlinked_cache_directory() {
        let directory = tempfile::tempdir().unwrap();
        let content = b"bytes";
        let file = metadata("plot.png", content);
        let digest = "a".repeat(64);
        let cache = directory.path().join("viewer-cache");
        fs::create_dir(&cache).unwrap();
        let outside = tempfile::tempdir().unwrap();
        std::os::unix::fs::symlink(outside.path(), cache.join(&digest)).unwrap();
        let transport = MockTransport::with_pages(
            vec![artifact_page(&digest)],
            vec![files_page(file.clone())],
            download(&file, content),
        );
        let opener = MockOpener::default();

        let error = open_committed_artifact_with(
            &origin(),
            "token",
            directory.path(),
            "run-1",
            "art-1",
            &file.file_id,
            &transport,
            &opener,
        )
        .await
        .unwrap_err();
        assert_eq!(
            error.code(),
            crate::error::HostErrorCode::HostBridgeUnavailable
        );
        assert!(opener.opened.lock().unwrap().is_empty());
        assert_eq!(transport.downloads(), 0);
    }
}
