(() => {
    "use strict";

    const root = document.querySelector("[data-reference-root]");
    if (!root) return;

    const search = root.querySelector("[data-reference-search]");
    const cards = Array.from(root.querySelectorAll("[data-reference-card]"));
    const sections = Array.from(root.querySelectorAll("[data-reference-section]"));
    const navLinks = Array.from(root.querySelectorAll(".reference-toc a[href^='#']"));
    const empty = root.querySelector("[data-reference-empty]");
    const tocToggle = root.querySelector("[data-reference-toc-toggle]");

    const normalize = (value) => String(value || "")
        .toLocaleLowerCase("ru-RU")
        .replace(/ё/g, "е")
        .replace(/\s+/g, " ")
        .trim();

    const revealTarget = (hash, shouldScroll = true) => {
        if (!hash || hash === "#") return;
        const target = root.querySelector(hash);
        if (!target) return;

        if (target.tagName === "DETAILS") {
            target.open = true;
        } else {
            const parentCard = target.closest("details[data-reference-card]");
            if (parentCard) parentCard.open = true;
        }

        if (shouldScroll) {
            window.requestAnimationFrame(() => target.scrollIntoView({ behavior: "smooth", block: "start" }));
        }
    };

    const runSearch = () => {
        const query = normalize(search?.value);
        let shown = 0;

        cards.forEach((card) => {
            const matches = !query || normalize(card.textContent).includes(query);
            card.hidden = !matches;

            if (query && matches) {
                if (!card.open) card.dataset.searchOpened = "true";
                card.open = true;
                shown += 1;
            } else if (!query && card.dataset.searchOpened === "true") {
                card.open = false;
                delete card.dataset.searchOpened;
                shown += 1;
            } else if (matches) {
                shown += 1;
            }
        });

        sections.forEach((section) => {
            const visibleCard = section.querySelector("[data-reference-card]:not([hidden])");
            section.hidden = Boolean(query) && !visibleCard;
        });

        if (empty) empty.hidden = shown > 0;
    };

    search?.addEventListener("input", runSearch);

    tocToggle?.addEventListener("click", () => {
        const opened = root.classList.toggle("toc-open");
        tocToggle.setAttribute("aria-expanded", String(opened));
    });

    navLinks.forEach((link) => {
        link.addEventListener("click", (event) => {
            const hash = link.getAttribute("href");
            if (hash && root.querySelector(hash)) {
                event.preventDefault();
                history.replaceState(null, "", hash);
                revealTarget(hash, true);
            }
            root.classList.remove("toc-open");
            tocToggle?.setAttribute("aria-expanded", "false");
        });
    });

    if (window.location.hash) revealTarget(window.location.hash, false);

    if ("IntersectionObserver" in window) {
        const observedTargets = sections.concat(cards.filter((card) => card.id));
        const observer = new IntersectionObserver((entries) => {
            const visible = entries
                .filter((entry) => entry.isIntersecting)
                .sort((a, b) => Math.abs(a.boundingClientRect.top) - Math.abs(b.boundingClientRect.top))[0];
            if (!visible) return;

            navLinks.forEach((link) => {
                link.classList.toggle("active", link.getAttribute("href") === `#${visible.target.id}`);
            });
        }, { rootMargin: "-18% 0px -72% 0px", threshold: 0 });

        observedTargets.forEach((target) => observer.observe(target));
    }
})();
