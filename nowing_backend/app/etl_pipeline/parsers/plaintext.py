def read_plaintext(file_path: str) -> str:
    # pi-lens-ignore: ast-grep:unchecked-throwing-call-python -- open failure propagates to caller
    with open(file_path, encoding="utf-8", errors="replace") as f:
        content = f.read()
    if "\x00" in content:
        raise ValueError(
            f"File contains null bytes — likely a binary file opened as text: {file_path}"
        )
    return content
