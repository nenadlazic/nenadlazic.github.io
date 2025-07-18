---
title: "Reactivity in Vue.js"
date: 2025-07-18
tags: ["vue.js", "reactivity", "frontend"]
categories: ["frontend"]
description: "vue js reactivity"
draft: false
---

One of the most powerful features of Vue.js and the reason why it feels so intuitive is its **reactivity system**. It allows your UI to automatically update when the underlying data changes, without writing a single line of manual DOM manipulation.

If you’ve ever built complex user interfaces before reactive frameworks like Vue, you know the pain of keeping the UI in sync with application state manually juggling query selectors, event handlers, and state flags. It's error-prone, hard to scale, and difficult to maintain.

Vue solves this elegantly by handling all those updates for you behind the scenes, so you can focus on what your app should do - not how to keep it visually in sync.

But how does this magic work under the hood? In this post, we’ll break down Vue’s reactivity system from Vue 2’s classic approach using getters/setters to the more powerful proxy-based model in Vue 3.

## What Is Reactivity?

When we talk about reactivity in programming, we mean a system that lets your code automatically adapt and respond to changes in data. Imagine it like this: instead of constantly checking manually whether something changed and then updating everything that depends on it, the reactive system does this for you behind the scenes, like a smart assistant quietly working in the background.

This approach simplifies managing state and data dependencies, making your code more maintainable and less error-prone.

In a nutshell, in the context of frontend:

> **When my data changes, my UI should reflect that change automatically.**

Vue achieves this by “watching” your data. When it sees a change, it updates the DOM in the most efficient way possible.

## How Vue’s Reactivity System Works: Vue 2 vs Vue 3

Vue’s reactivity system is the backbone of the framework. Over the years, Vue has evolved this system from Vue 2 to Vue 3, improving flexibility, performance, and developer experience.

- **Vue 2: reactivity with getters and setters**

    In Vue 2, reactivity is implemented by defining **getters** and **setters** on each property of the data object using JavaScript’s `Object.defineProperty()`. This allows Vue to:
    - Track when a property is **read** (getter)
    - Detect when a property is **written to or updated** (setter)

    When a property changes, Vue knows exactly which components or computed properties depend on that specific piece of data. It does this by tracking dependencies during the component’s render phase, collecting "watchers" that observe the data. 
    When a component renders or accesses a reactive value, Vue registers (collects) a watcher for that value, keeping track of which parts of the application need to be updated when that value changes.
    Then, when the data changes, Vue efficiently triggers updates only on those components that actually rely on the changed data, avoiding unnecessary re-renders of unaffected parts of the UI. This fine-grained dependency tracking is what makes Vue both performant and responsive.

    **Limitations of Vue 2 reactivity:**
    - Vue 2 **cannot detect new properties added to an object** after its initialization, so you need to use `Vue.set()` to add reactive properties dynamically
    - Deleting properties also is **not reactive** by default
    - Reactivity with arrays requires special methods like `splice()` or `Vue.set()` for updates to be tracked
    - The system adds some overhead by creating getters and setters for each property

    Despite these limitations, Vue 2’s reactivity system was revolutionary for its time, simplifying UI synchronization significantly compared to manual DOM manipulation.

- **Vue 3: modern reactivity with proxy**

    Vue 3 rebuilds the reactivity system using JavaScript’s Proxy API, which **wraps** the entire object and intercepts all operations instead of only individual properties. This lets Vue detect reads, writes, additions, and deletions seamlessly. When the reactive object changes, Vue precisely tracks what was modified and updates only the affected computations and UI.

    This approach offers several advantages:

    - **Full observation** of properties, including additions, deletions, and nested objects, without needing `Vue.set()`
    - **Improved performance** due to less overhead in tracking changes
    - **Simpler and cleaner internal code**, which also enables advanced features like the Composition API
    - Reactivity works seamlessly with complex data structures

    **Simple Vue 3 reactive component example**

    ```vue
    <template>
    <div>
        <p>Count: {{ count }}</p>
        <button @click="increment">Increase</button>
    </div>
    </template>

    <script setup>
    import { ref } from 'vue'

    const count = ref(0)

    function increment() {
    count.value++
    }
    </script>

    <style scoped>
    button {
    padding: 5px;
    }
    </style>
    ```

    This is a minimal Vue 3 component example demonstrating reactive state using ref, which creates a reactive data variable (count). The UI automatically updates whenever the count value changes after clicking the button.


### Summary Table

| Feature                     | Vue 2 (Getters/Setters)            | Vue 3 (Proxy)                         |
|-----------------------------|-----------------------------------|-------------------------------------|
| Detect property addition    | No (requires `Vue.set()`)         | Yes                                 |
| Detect property deletion    | No                                | Yes                                 |
| Nested objects reactivity   | Yes, but with caveats              | Yes, fully reactive                 |
| Performance                | Good, but with overhead per property | Better, proxy-based and optimized   |
| Ease of use                | Some workarounds needed            | Cleaner, more intuitive              |

---

## Wrap-Up

Vue’s reactivity system is the secret sauce behind its ease of use and powerful capabilities. The evolution from Vue 2’s getters/setters to Vue 3’s Proxy-based reactivity brings better performance, fewer caveats, and more flexibility - all while making your development experience smoother.

In the next post, we’ll dive into Vue 3’s **Composition API**, which leverages this reactive core to help you organize and reuse your application logic efficiently.
