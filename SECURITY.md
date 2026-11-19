# Security policy

## Supported versions

Only the latest release gets fixes. Older releases are not patched; install the latest one from the [releases page](https://github.com/phabzlabz/digital-rain/releases/latest).

## Reporting a vulnerability

Please do not report security problems in a public issue. Use GitHub's private vulnerability reporting instead: open the repository's Security tab and choose "Report a vulnerability". Include the version, your operating system and the steps to reproduce.

You should get a first reply within two weeks. This is a hobby project with no bug bounty.

## Scope

The screensaver reads a local settings file, an optional font file and an optional folder of pictures, and it never connects to the network. Problems worth reporting include a crafted settings file, font or picture that makes it run code, and a release download that does not match the source. Releases carry `SHA256SUMS.txt` and build provenance attestations (`gh attestation verify <file> -R phabzlabz/digital-rain`), so a file you downloaded can be checked against the workflow run that built it. The Windows installer is not code-signed and the Mac saver is not notarised, so a SmartScreen or Gatekeeper warning on its own is expected and not a vulnerability.
