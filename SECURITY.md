# Security Policy

## Reporting a Vulnerability

If you believe you have found a security vulnerability in the Friday Agent SDK,
please report it privately. **Do not open a public GitHub issue.**

Email: **security@hellofriday.ai**

Please include:

- A description of the vulnerability and its potential impact
- Steps to reproduce (proof-of-concept code, affected versions, environment)
- Any suggested mitigation

We will acknowledge your report within 3 business days and provide an estimated
timeline for a fix. We ask that you give us a reasonable window to investigate
and patch before any public disclosure.

## Supported Versions

Security fixes are applied to the latest released version on `main`. Older
versions are not supported.

## Scope

In scope:

- The `friday_agent_sdk` Python package (`packages/python/`)
- Build and release tooling in this repository

Out of scope (please report to the appropriate project):

- The Friday daemon and `atlas` CLI — see [friday-platform/friday-studio](https://github.com/friday-platform/friday-studio)
- Third-party dependencies — please report directly to the upstream project
