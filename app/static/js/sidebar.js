(() => {
    "use strict";

    const sidebar = document.getElementById("appSidebar");
    const toggle = document.getElementById("sidebarToggle");
    const backdrop = document.getElementById("sidebarBackdrop");
    if (!sidebar || !toggle || !backdrop) return;

    const body = document.body;
    const desktopQuery = window.matchMedia("(min-width: 992px)");
    const storageKey = "misSidebarCollapsed";

    const setExpandedState = (expanded) => {
        toggle.setAttribute("aria-expanded", String(expanded));
    };

    const closeMobileSidebar = () => {
        body.classList.remove("sidebar-mobile-open");
        backdrop.hidden = true;
        setExpandedState(false);
    };

    const openMobileSidebar = () => {
        body.classList.add("sidebar-mobile-open");
        backdrop.hidden = false;
        setExpandedState(true);
    };

    const applyViewportState = () => {
        if (desktopQuery.matches) {
            body.classList.remove("sidebar-mobile-open");
            backdrop.hidden = true;
            const collapsed = window.localStorage.getItem(storageKey) === "1";
            body.classList.toggle("sidebar-collapsed", collapsed);
            setExpandedState(!collapsed);
        } else {
            body.classList.remove("sidebar-collapsed", "sidebar-mobile-open");
            backdrop.hidden = true;
            setExpandedState(false);
        }
    };

    toggle.addEventListener("click", () => {
        if (desktopQuery.matches) {
            const collapsed = body.classList.toggle("sidebar-collapsed");
            window.localStorage.setItem(storageKey, collapsed ? "1" : "0");
            setExpandedState(!collapsed);
            return;
        }

        if (body.classList.contains("sidebar-mobile-open")) {
            closeMobileSidebar();
        } else {
            openMobileSidebar();
        }
    });

    backdrop.addEventListener("click", closeMobileSidebar);
    sidebar.addEventListener("click", (event) => {
        if (!desktopQuery.matches && event.target.closest("a")) closeMobileSidebar();
    });
    document.addEventListener("keydown", (event) => {
        if (event.key === "Escape" && body.classList.contains("sidebar-mobile-open")) {
            closeMobileSidebar();
            toggle.focus();
        }
    });

    if (typeof desktopQuery.addEventListener === "function") {
        desktopQuery.addEventListener("change", applyViewportState);
    } else {
        desktopQuery.addListener(applyViewportState);
    }

    applyViewportState();
})();
