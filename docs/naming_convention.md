# Naming Convention

This repository and its related projects use a consistent naming convention for clarity and maintainability. They are included here as submodules with abbreviated names.


All repositories start with the **product prefix**:

```text
cl_server_
```

After the prefix, names follow this structure:

```text
cl_server_<role>_<scope | runtime | function>_<optional extended names>
```

Where:

* `<role>` describes *what the repository is*
* The remaining parts describe *how or where it is used*
    > **If it is a backend → `*_service`**  
    > **If it is a library → `sdk_*`**  
    > **If it is executable → `cli_*` or `ui_*`**


## 🖥 Server Services

Server services represent backend components that are deployed independently. They must all be hosted on the same machine on different ports, as they share common resources.

```text
cl_server_<service>_service
```

Currently available services:

```text
cl_server_auth_service
cl_server_compute_service
cl_server_store_service
```

---

## SDKs (Software Development Kits)

**SDKs** are language-specific libraries used by applications or integrations to communicate with the server APIs.

```text
cl_server_sdk_<runtime>
```

Currently supported SDKs:

```text
cl_server_sdk_python
cl_server_sdk_dart
```

* SDKs are **libraries**, not executables
* One SDK per language/runtime

---

## Demo Applications (CLI / UI)

Demo applications are reference applications built on top of the SDKs. Their purpose is to showcase cl_server features and recommended usage patterns.

Production applications are **not required** to follow this naming scheme.

```text
cl_server_<app_type>_<runtime>
```

Where `<app_type>` is one of:

* `cli` – Command-line application
* `ui` – Graphical / visual application

Currently Available Demo Applications

| Repository Name        | Type | Runtime | Status / Purpose                                |
| ---------------------- | ---- | ------- | ----------------------------------------------- |
| `cl_server_cli_python` | CLI  | Python  | Development in progress                         |
| `cl_server_cli_dart`   | CLI  | Dart    | Development in progress                         |
| `cl_server_ui_flutter` | UI   | Flutter | UI app demonstrating various cl_server features |
