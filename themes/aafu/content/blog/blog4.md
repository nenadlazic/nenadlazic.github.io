---
title: "Getting Started with Vue.js"
date: 2025-07-04
tags: ["vue.js", "webdev"]
categories: ["frontend"]
description: "vue js intro"
draft: false
---
## What is Vue.js?
Vue is a powerful yet easy-to-use JavaScript framework that lets you build dynamic, interactive user interfaces with ease. It works with standard HTML, CSS, and JavaScript, leveraging a clean, component-based structure that helps you craft everything from simple page elements to fully-featured, complex applications — all without the headache.

At its core, Vue.js is a progressive framework. It offers incremental adoptability, meaning you can start small by enhancing just a tiny part of your webpage and gradually scale it up to build complete, modern web apps — no need to rewrite everything from scratch!

## Why use it?
Vue is:

- 🪶 Lightweight – small in size and fast to load
- 🧠 Easy to learn – especially if you know basic HTML, CSS, and JavaScript
- 🧩 Great for SPA – apps that feel like desktop programs but run in your browser

🔍 How does it compare to React and Angular?

- React is flexible but requires more setup and learning around the environment.
- Angular is powerful but complex and mostly suited for big enterprise projects.
- Vue sits in between — offering structure and simplicity without being overwhelming.
- Vue lets you quickly build working applications, making it a great choice for both beginners and experienced developers.

## Setting up development environment

To start building applications with Vue.js, a few tools need to be installed and configured. Each of them plays a specific role in the development process. Essential tools for Vue app development:

- **Node.js** - JavaScript runtime environment that allows JavaScript code to run outside of a web browser (directly on your computer or server) and comes with **npm**, a package manager used to install and manage libraries like Vue. Node.js is needed for Vue.js development because it allows tools like Vite or Vue CLI to run, install packages, and start the development server.
- **NVM** - Node Version Manager is a tool that allows easy installation and switching between multiple Node.js versions on one machine. It helps manage different project requirements without conflicts. 
- **Vite** - is a modern build tool that helps start and run Vue projects quickly. It provides a fast development server and updates the app instantly as you make changes, making development smooth and efficient.
- **Vue DevTools** -  is a browser extension for inspecting and debugging Vue.js apps. It shows component trees, reactive data, and events to simplify development.

Step-by-Step Setup on Linux:
 1. Install NVM (Node Version Manager)
    ```bash
    # download and execute the installation script
    curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.7/install.sh | bash
    source ~/.bashrc
    ```
 2. Install Node.js (via NVM)
    ```bash
    nvm ls-remote # List available Node.js versions that can be installed
    nvm install 21 # Install the desired Node.js version, e.g., 21
    nvm use 21 # Switch to use the selected Node.js version in the current session
    node -v # Check the installed Node.js version
    npm -v # Check the installed npm version
    ```
 3. Create a Vue project with Vite
    ```bash
    npm create vite@latest my-vue-app -- --template vue   # Create a new Vue project with Vite template
    cd my-vue-app                                         # Navigate into the newly created project directory
    npm install                                           # Install all project dependencies listed in package.json
    npm run dev                                           # Start the development server with hot reload enabled
    ```
 4. (Optional) Install Vue DevTools
   
    Get the Vue DevTools extension for Chrome or Firefox to inspect and debug Vue apps easily.

🎉 If everything went well, your very first Vue.js app should now be successfully running on localhost.


## What you learned?

## What's Next?
