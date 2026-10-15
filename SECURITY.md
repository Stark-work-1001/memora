# Security policy

Memory Merge stores private material by design, so security reports are welcome.

## Reporting

Please report vulnerabilities privately through GitHub's "Report a vulnerability"
(Security -> Advisories) on https://github.com/Stark-work-1001/memory-merge, not in a public issue.
Include the version (`memory-merge --version`), the output of `memory-merge doctor` (it contains no
memory content), and steps to reproduce. Do not include real memories or credentials.

This is a volunteer-maintained alpha: there is no guaranteed response time. Supported versions: the
latest release only.

## In scope

Anything that breaks a property in [docs/THREAT_MODEL.md](docs/THREAT_MODEL.md), for example:

- an MCP capture client approving memory or reading pending, rejected or deleted content;
- stored or imported content escaping its evidence block or being executed as instructions by the
  system itself;
- network access without explicit configuration;
- a website driving the local viewer;
- content surviving `purge` inside the data directory;
- path traversal or SMB/UNC access through imports.

## Out of scope

Attacks by other processes running as the same OS user, a user approving a malicious memory,
secrets that match no screening pattern (documented limitation), and remote model providers' own
handling of data you chose to send them.
