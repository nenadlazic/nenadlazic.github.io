---
title: "Keycloak migration scripts: your shortcut to consistent IAM"
date: 2025-08-14
tags: ["keycloak", "security", "backend"]
categories: ["security"]
description: "writing keycloak migration scripts"
draft: false
---

## Introduction

Managing authentication and authorization at scale can be error-prone. Manual clicks in the Keycloak dashboard work for small environments, but as your system grows, replicating configurations across development, staging, and production becomes tedious and risky.

Keycloak migration scripts let you treat your IAM configuration as code: versioned, repeatable, and automatable. With scripts, you can apply changes safely, track them in version control, and integrate them into CI/CD pipelines for consistent deployments.

## Why Migration Scripts Matter?

Migration scripts make Keycloak management faster, safer, and more consistent. Instead of manual clicks, you automate repetitive tasks, keep environments in sync, and maintain a clear audit trail of changes.

 Typical use cases include:

- Migrating users, groups, and roles between Keycloak instances
- Replicating realm settings across development, staging, and production environments
- Bulk-creating service accounts and client roles
- Backing up and restoring configurations for disaster recovery

Treat Keycloak as code, not clicks. Scripts reduce human errors, speed up deployments, and ensure your identity infrastructure scales reliably with your applications.

## How Keycloak migration scripts work

There are two main ways to manage Keycloak migration scripts, depending on whether you need incremental changes or full realm migrations:

1. **Using the Keycloak REST API from your local machine**
	 - Tools like kcadm.sh (Keycloak Admin CLI) let you authenticate to a remote Keycloak server and perform administrative tasks such as creating users, clients, or roles directly from your terminal. This approach is ideal for incremental, scriptable changes and CI/CD automation, as it does not require direct server access, only network/API access and sufficient credentials.
	 - Example:
		 ```bash
		 kcadm.sh config credentials --server https://<keycloak-server>/ --realm master --user <admin-username> --password <admin-password>
        kcadm.sh create users -r <realm-name> -s username=newuser -s enabled=true
		 ```
	 - You can also use `curl` or Postman to make direct REST API requests for fine-grained migrations.

     In short: Use kcadm.sh for targeted updates and automation.

2. **Running CLI scripts directly on the server or in the Docker container**
	 - For full realm migrations or bulk updates, use Keycloak CLI (kc.sh) inside the environment where Keycloak is deployed (e.g. Docker container or VM). This allows you to export or import entire realm configurations as JSON files. This method is perfect for backups, full environment replication, or disaster recovery.

	 - Example (Docker):
		 ```bash
		 docker exec <container-name> /opt/keycloak/bin/kc.sh export --realm <realm-name> --file /tmp/realm-export.json
		 docker cp <container-name>:/tmp/realm-export.json ./realm-export.json
		 docker cp ./realm-export.json <container-name>:/tmp/realm-export.json
		 docker exec <container-name> /opt/keycloak/bin/kc.sh import --file /tmp/realm-export.json
		 ```

    In short: Use kc.sh export/import for full migrations or backups.

    ### Behind the scenes & best practices

    When you run Keycloak migration scripts, whether via kcadm.sh, REST API, or kc.sh, you’re essentially talking to the Keycloak server programmatically. Here’s a simplified view of what happens:
    1. Authentication – Your script logs in as an admin or service account, making sure it has the right permissions.
    2. Payload creation – Each command is turned into a JSON payload representing the configuration you want (users, roles, clients, groups, etc.).
    3. Server processing – Keycloak applies your changes to its database, validating relationships and dependencies.
    4. Persistence – All changes are saved in the database and reflected in the running system.
    5. Automation-friendly – Scripts can be integrated into CI/CD pipelines, making deployments repeatable, auditable, and safer.

    #### Key tips:

    - Always test scripts in non-production environments first.
    - Use kcadm.sh for incremental updates and CI/CD automation.
    - Use kc.sh export/import for full backups or bulk migrations.
    - Be cautious: importing a realm JSON can overwrite existing configurations.

    Migration scripts turn what used to be manual clicks into automated, reliable operations, letting you manage Keycloak as code.


## Practical examples: Writing migration scripts

Here are clear examples showing how to automate common Keycloak tasks with migration scripts and CLI tools. You can use them for initial setup, incremental updates, or CI/CD automation.

### 1. Creating a client (resource server)

```bash
# Step 1: Authenticate to Keycloak
kcadm.sh config credentials \
    --server https://<keycloak-server>/ \
    --realm master \
    --user <admin-username> \
    --password <admin-password>

# Step 2: Create the resource server client
kcadm.sh create clients -r <realm-name> \
    -s clientId=<resource-server-name> \
    -s protocol=openid-connect \
    -s publicClient=false \
    -s directAccessGrantsEnabled=true \
    -s serviceAccountsEnabled=true
```
This creates a confidential client that can request tokens using username/password (directAccessGrantsEnabled=true) and can also use a service account to access other services (serviceAccountsEnabled=true).

There are additional parameters you can set depending on your needs, such as standardFlowEnabled, implicitFlowEnabled, clientAuthenticatorType, redirectUris, rootUrl, and attributes. These allow further customization, for example enabling browser-based login, defining redirect URIs, or setting specific client attributes.

### 2. Adding roles to a realm

```bash
# Add a new role to the realm
kcadm.sh create roles -r <realm-name> \
    -s name=<role-name>
```
Roles define permissions that can be assigned to users, groups, or clients. You can create multiple roles and manage access consistently across environments without using the UI.

### 3. Assigning a role to a user

```bash
# Assign role to a user
kcadm.sh add-roles -r <realm-name> \
    --uusername <username> \
    --rolename <role-name>
```
This allows automation of user-role assignments, which is especially useful for provisioning test users or syncing environments.

### 4. Creating and assigning client scopes

```bash
# Create a client scope
kcadm.sh create client-scopes -r <realm-name> \
    -s name=<scope-name> \
    -s protocol=openid-connect

# Assign the scope to a client
kcadm.sh update clients/<client-id> -r <realm-name> \
    -s 'defaultClientScopes=["<scope-name>"]'
```

Client scopes define sets of claims or permissions for clients. Automating their creation ensures consistent behavior across environments.


## Conclusion

Migration scripts turn what used to be manual UI clicks into repeatable, version-controlled, and automated operations. By scripting clients, roles, user assignments, and scopes, you can:

- Reduce human errors and inconsistencies
- Keep multiple environments synchronized
- Integrate Keycloak configuration into CI/CD pipelines

Treat Keycloak as code, not clicks, and you’ll gain both reliability and scalability in your identity and access management workflows.