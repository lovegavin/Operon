//! Real loopback HTTP, the studio authentication convention, and verified reuse.
use operon_desktop_experimental::artifacts::{
    open_committed_artifact_with, PathOpener, ReqwestArtifactTransport,
};
use sha2::{Digest, Sha256};
use std::{
    io::{Read, Write},
    net::TcpListener,
    path::{Path, PathBuf},
    sync::Mutex,
    time::{Duration, Instant},
};
use url::Url;

#[derive(Default)]
struct Recorder(Mutex<Vec<PathBuf>>);
impl PathOpener for Recorder {
    fn open(&self, path: &Path) -> Result<(), ()> {
        self.0.lock().unwrap().push(path.to_owned());
        Ok(())
    }
}

#[tokio::test]
async fn studio_authentication_download_and_verified_cache_over_http() {
    let content = b"sample,value\na,1\n";
    let digest = format!("{:x}", Sha256::digest(content));
    let file_id = "f".repeat(64);
    let listener = TcpListener::bind("127.0.0.1:0").unwrap();
    let origin = Url::parse(&format!("http://{}/", listener.local_addr().unwrap())).unwrap();
    listener.set_nonblocking(true).unwrap();
    let server_digest = digest.clone();
    let server_id = file_id.clone();
    let server = std::thread::spawn(move || {
        let mut downloads = 0;
        for index in 0..5 {
            let deadline = Instant::now() + Duration::from_secs(10);
            let mut stream = loop {
                match listener.accept() {
                    Ok((stream, _)) => break stream,
                    Err(error)
                        if error.kind() == std::io::ErrorKind::WouldBlock
                            && Instant::now() < deadline =>
                    {
                        std::thread::sleep(Duration::from_millis(10))
                    }
                    Err(error) => panic!("request {index}: {error}"),
                }
            };
            stream
                .set_read_timeout(Some(Duration::from_secs(3)))
                .unwrap();
            let mut request = Vec::new();
            while !request.ends_with(b"\r\n\r\n") {
                let mut byte = [0];
                stream.read_exact(&mut byte).unwrap();
                request.push(byte[0]);
                assert!(request.len() < 8192);
            }
            let request = String::from_utf8(request).unwrap();
            assert!(request
                .to_ascii_lowercase()
                .contains("x-studio-token: fixture-studio-secret\r\n"));
            assert!(!request.to_ascii_lowercase().contains("authorization:"));
            let path = request.split_whitespace().nth(1).unwrap();
            let (body, media) = if path.contains("/open") {
                downloads += 1;
                assert_eq!(
                    path,
                    format!("/api/v1/plans/run-1/artifacts/art-1/files/{server_id}/open")
                );
                (content.to_vec(), "text/csv")
            } else if path.contains("/files") {
                (serde_json::to_vec(&serde_json::json!({"run_id":"run-1","revision":1,"artifact_id":"art-1","files":[{"file_id":server_id,"name":"data.csv","size_bytes":content.len(),"sha256":server_digest,"media_type":"text/csv"}],"next_cursor":"file-1","has_more":false})).unwrap(), "application/json")
            } else {
                (serde_json::to_vec(&serde_json::json!({"run_id":"run-1","revision":1,"artifacts":[{"artifact_id":"art-1","sha256":server_digest}],"next_cursor":"art-1","has_more":false})).unwrap(), "application/json")
            };
            write!(stream, "HTTP/1.1 200 OK\r\nContent-Length: {}\r\nContent-Type: {media}\r\nConnection: close\r\n\r\n", body.len()).unwrap();
            stream.write_all(&body).unwrap();
        }
        assert_eq!(downloads, 1);
    });
    let profile = tempfile::tempdir().unwrap();
    let transport = ReqwestArtifactTransport::new().unwrap();
    let opener = Recorder::default();
    for _ in 0..2 {
        open_committed_artifact_with(
            &origin,
            "fixture-studio-secret",
            profile.path(),
            "run-1",
            "art-1",
            &file_id,
            &transport,
            &opener,
        )
        .await
        .unwrap();
    }
    server.join().unwrap();
    let opened = opener.0.lock().unwrap();
    assert_eq!(opened.len(), 2);
    assert_eq!(opened[0], opened[1]);
    assert_eq!(std::fs::read(&opened[0]).unwrap(), content);
}
