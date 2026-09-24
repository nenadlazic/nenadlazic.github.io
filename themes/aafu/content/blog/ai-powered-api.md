---
title: "Understanding AI-powered backends"
date: 2025-09-19
tags: ["spring boot", "llm", "ollama", "docker", "java"]
categories: ["backend", "ai", "llm"]
description: "The architect's mental model for AI-powered backends: what LLMs and agents really are, the cloud-vs-self-hosted decision, and the engineering you wrap around the model."
cover: "/images/og/ai-powered-api.png"
draft: false
---

Large Language Models (LLMs) have become the backbone of modern AI: they can generate text, summarize documents, answer questions, and help automate developer workflows.

But here is the framing that matters for anyone designing systems: **an LLM is just another component - only an unusual one.** It is probabilistic (the same input can return different output), stateless (it remembers nothing between calls), and it can be confidently wrong. Almost everything we call an "AI-powered backend" is the engineering we wrap *around* that component to make it useful and reliable: memory, facts, actions, and guardrails.

This post is the mental model before the build - deliberately high-level. We'll cover:
- How LLMs work, and what they can (and can't) do
- What AI agents are, and how they differ from a plain LLM call
- The real challenges of putting an LLM behind an API
- Why and when self-hosting buys you privacy, control, and lower cost

Later posts in this series turn these ideas into a working service. This one is about getting the architecture straight first.

## The shape of an AI-powered backend

Before the concepts, here is the picture worth keeping in your head:

![Anatomy of an AI-powered backend: a client request flows through your API and orchestration layer to the LLM, with privacy, cost, latency, guardrails, and observability as cross-cutting concerns](/images/ai-powered-backend-anatomy.png)

The model is just one box. Everything else in that picture is yours to design - and it is where reliability is won or lost.

## Understanding LLMs, AI Agents, and Challenges

### What are LLMs?
Large Language Models (LLMs) are neural networks trained on massive text datasets to predict the next chunk of text, called a token (which can be a word, part of a word, or punctuation). By learning these patterns, LLMs can generalize and adapt to a wide variety of contexts, drawing on the knowledge and examples seen during training.

Thanks to this, they can:
- Generate natural language (answers, summaries, explanations)
- Follow prompts to perform tasks like translation, extraction, or formatting
- Adapt to context through prompt design or a few examples (few-shot learning)

Important caveat: LLMs can “hallucinate” - confidently produce incorrect or invented facts and their knowledge can be outdated unless connected to live data.

### What are AI Agents?

An **AI agent** is a system that uses a language model (LLM) as its “brain” but also takes **autonomous actions** based on input and context. Unlike a plain LLM integration, which only generates text, an agent can make decisions, orchestrate multiple steps, and interact with external tools or data sources.

In practice, an agent typically:
- Analyzes input data to decide how to proceed
- Calls LLM(s) intelligently, sometimes multiple times, to generate or refine content
- Interacts with external systems such as databases, APIs, or workflows to gather information or perform actions
- Produces structured outputs or triggers side effects in your application

In short, an AI agent is **LLM + orchestration + autonomous decision-making**, turning raw text generation into actionable, context-aware automation.

The architectural catch: every bit of autonomy you hand an agent is a bit of determinism you give up. More steps and more tool access mean more capability - and a larger surface for things to go wrong. Taming that surface is the hard part, and the subject of later posts in this series.


## Self-Hosted LLMs

When starting to build AI-powered backends, many developers first try **cloud-based LLM APIs** like OpenAI, Gemini, or Claude. This approach is attractive because it’s fast and easy: you get a pre-trained model with minimal setup - just an API key and a few lines of code.

However, this approach has trade-offs. The decision is really cloud vs self-hosted, and it comes down to a few axes:

| Concern | Cloud LLM API | Self-hosted LLM |
|---|---|---|
| **Cost** | Pay-per-token, scales with usage | Fixed hardware cost, cheaper at volume |
| **Privacy / control** | Data leaves your perimeter; you rely on the provider's terms | Prompts and data stay in-house by construction |
| **Latency** | Network round-trip per call | Local, no egress hop |
| **Setup** | API key, ready in minutes | Provision compute, manage the runtime |

A fair caveat on that privacy row, because it is easy to overstate in either direction. The serious providers offer enterprise terms - data-processing agreements, zero-retention endpoints, and commitments not to train on your traffic - and for many workloads that is genuinely enough. But be precise about what you are buying: a *contractual* guarantee, not a technical one. Your data still leaves your network, a third party still processes it, and that party is an added attack surface - breaches and misconfigurations happen to everyone. Self-hosting does not make you magically secure; it changes the question from "do I trust their promise and their security?" to "do I trust my own?" - and for regulated or highly sensitive data, removing the third party entirely is sometimes the only answer that passes an audit.

Once the cost, privacy, or latency rows start to hurt, moving to private or local deployment becomes appealing.

You don’t need a supercomputer to run a self-hosted LLM. Depending on the model size, a modern workstation or small server may suffice. Tools like **Ollama** provide a simple runtime to run pre-trained models in Docker under your control.

Key points to know:
- Pre-trained models (e.g., LLaMA, Mistral, Falcon) can be pulled and run without cloud dependencies
- Self-hosting requires sufficient compute and memory: smaller models run comfortably on a single GPU or CPU-heavy machines, while larger models need more resources
- You have full control over your data: prompts, fine-tuning datasets, and queries never leave your infrastructure

With this setup, your backend can interact with the model as if it were any other internal service - private, fast, and flexible.

##  Pre-trained Models and Fine-Tuning 

Once you decide to self-host a model, the next step is choosing and adapting the model for your use case. There are several approaches:

### 1. Pre-trained Models
Open-source LLMs like LLaMA, Mistral, Falcon, and others come ready to use. They offer:
- Immediate usability: start generating text or building agents without training from scratch
- Active community support: tutorials, examples, and pre-trained checkpoints

Limitations include model size, licensing restrictions, and sometimes limited domain-specific knowledge.

### 2. Fine-Tuning Existing Models
Fine-tuning lets you adapt a pre-trained model to your own data or domain:
- Techniques like LoRA (**Low-Rank Adaptation**), PEFT (**Parameter-Efficient Fine-Tuning**), or **instruction tuning** modify only a small subset of the model’s parameters instead of retraining the entire network.

- LoRA: trains small “adapter” matrices that are added to the existing weights, allowing the model to learn new tasks without full retraining.
- PEFT: a general approach that fine-tunes only selected parts of the model to save memory and computation while adapting to specific tasks.
- Instruction tuning: fine-tunes the model on prompts with instructions, making it better at following task-specific guidance.

Fine-tuned models retain their general language abilities while becoming specialized for your target tasks, providing domain-specific intelligence without the need for huge computational resources.

### 3. Training from Scratch
This is usually only practical for research or very specialized projects. It requires massive datasets and significant computational resources.

Key takeaway: for most projects, the practical workflow is to pick a pre-trained model, optionally fine-tune it for your domain, and deploy it in a self-hosted setup for full privacy, control, and low latency.

## Conclusion
If there is one thing to take from this post, it is the framing: **the LLM is the easy part.** Pulling a model and getting text back is a few lines of code. The architecture is everything around it - choosing cloud vs self-hosted, keeping data private, controlling cost and latency, and putting guardrails between a probabilistic component and your users.

Get that shape right, and the rest of this series is just filling it in.

## Next Steps
In the next posts, we’ll build a complete AI agent that integrates with a self-hosted LLM. You’ll see how to:
- Send structured queries from your API to the local model
- Receive and process responses
- Orchestrate multiple tasks, turning raw LLM outputs into actionable, context-aware automation

This will transform the concepts covered here into a working, private AI-powered service that you can run, test, and extend.