---
title: "Authentication vs Authorization Explained"
date: 2025-07-04
tags: ["security", "authentication", "authorization"]
categories: ["backend"]
description: "Understand the key difference between authentication and authorization, why it matters, and how to avoid common pitfalls."
draft: false
---

## Introduction – Why This Matters
Security is one of the most critical aspects of backend development, yet the concepts of authentication and authorization are often confused or mixed up. No matter if you're building a web application, a REST API, or a distributed microservices system, it's essential to know **who the user is** and **what they're allowed to do**. This blog post will explain these two fundamental concepts in plain terms, outline how they work together, and offer best practices every backend developer should follow to build secure applications.

## What is Authentication?
**Authentication** is the process of verifying **who the user is**. It answers the crucial question: _"Are you really who you claim to be?"_

Typically, this involves the user providing credentials that your system can validate, such as a password, a fingerprint, or a token. On the backend, your system validates these credentials to confirm the user's identity, usually by comparing them to stored information. Once a user is successfully authenticated, they gain access to the system. However, what they can actually do within that system is then determined by **authorization**.

It's also common for backend systems to delegate this entire authentication process to third-party identity providers like Keycloak, Auth0, Okta or even social logins (Google, Facebook), which manage user identities and issue tokens. These services manage user identities and issue tokens, effectively offloading the complexity of secure credential storage and verification from your application.

### Common authentication methods:

Modern applications support a variety of authentication methods, each designed for specific use cases—from simple user logins to secure machine-to-machine communication. Understanding these methods helps you choose the right level of security and user experience for your application. Below are the most commonly used approaches:

- **Username and password**

    Is the most common login method. Users enter a username (or email) and password, which is verified against a securely hashed version in the database.

    | ✅ Pros                 | ❌ Cons                                     | 🛡️ Tips                          |
    |------------------------|---------------------------------------------|----------------------------------|
    | Simple to implement    | Weak alone                                  | Hash passwords    |
    | Universally supported  | Prone to phishing and brute-force attacks  | Enforce strong passwords        |
    | Familiar to all users  | Users often use weak or reused passwords  | Add MFA for better security     |


- **Multi-Factor Authentication (MFA)**

    Adds an extra layer of security by combining different types of verification factors—**something you know** (like a password), **something you have** (such as a phone or hardware token), or **something you are** (biometric data). This multi-layered approach makes it much harder for attackers to gain access to an account, even if one factor is compromised.
    | ✅ Pros                                         | ❌ Cons                                    | 🛡️ Tips                                    |
    |------------------------------------------------|--------------------------------------------|--------------------------------------------|
    | Significantly increases security                | Adds extra steps for users                   | Use authenticator apps or hardware tokens  |
    | Protects against stolen passwords                | Requires additional setup and maintenance   | Encourage users to enable MFA               |
    | Supports multiple verification methods (apps, biometrics, hardware) | Security depends on the strength of second factor | Avoid SMS when possible                      |


- **OIDC (OpenID Connect on top of OAuth2)**

    While OAuth2 is primarily an authorization framework, OpenID Connect (OIDC) builds on top of it to provide authentication — allowing applications to verify a user’s identity based on a trusted identity provider (e.g., Google, Microsoft, Keycloak).

    An identity provider (IdP) is a service that authenticates users and issues identity tokens on their behalf. It acts as a trusted source of truth about user identities, allowing applications to offload the responsibility of login and user management.
    Popular identity providers include Google, Microsoft, Keycloak, Auth0, and Okta.
    
    After the user logs in through the identity provider, the application receives a signed ID token (usually a JWT), which it sends to the backend — where the token is validated to confirm the user’s identity and extract relevant user info.



- SAML (Security Assertion Markup Language):
- Biometric authentication (e.g. fingerprint, face ID)
- API keys or certificates (machine-to-machine)

### Tips for choosing an authentication method:
- **Balance security and usability:** Stronger methods like MFA offer more security, but may affect user experience.
- **Use industry standards** whenever possible (e.g., OAuth2 + OpenID Connect for web/mobile apps).
- **Avoid implementing your own auth:** Leverage trusted identity providers (e.g., Keycloak, Auth0, Okta).
- **Different contexts need different methods:** Use API keys or mutual TLS for backend systems, and username/password + MFA for user-facing apps.
- **Protect secrets:** Whether it’s passwords, tokens, or certificates—always store them securely.

##  What is Authorization?
### Common models:
- Role-Based Access Control (RBAC)
- Attribute-Based Access Control (ABAC)
- Scope-Based Authorization (used in OAuth2)
- Ownership-Based Authorization

## How Authentication and Authorization Work Together

##  Protocols & Standards You Should Know
- OAuth2
- OpenID Connect (OIDC)
- SAML (Security Assertion Markup Language)

## Common Pitfalls and Misconceptions

## Security Best Practices

## Summary

## What’s Next?
