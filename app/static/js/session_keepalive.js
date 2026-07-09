/*
Назначение файла: клиентская защита от потери введённых данных при истечении сессии.

Как работает:
- отслеживает реальную активность врача: ввод, клики, изменение полей;
- раз в SESSION_KEEPALIVE_INTERVAL_SECONDS отправляет POST /auth/session/keepalive,
  но только если врач действительно что-то делал;
- перед отправкой любой формы проверяет /auth/session/status;
- если сессия истекла, форма НЕ отправляется, введённые данные остаются на странице,
  а врач видит предупреждение и может войти снова в новой вкладке.

Что редактировать здесь:
- тексты предупреждений;
- список событий активности;
- визуальный вид banner-уведомления.

Что не редактировать здесь:
- правила проверки пароля;
- серверный idle-timeout;
- медицинскую логику форм.
*/

(function () {
    "use strict";

    var keepaliveIntervalSeconds = Number(window.MIS_SESSION_KEEPALIVE_INTERVAL_SECONDS || 180);
    var checkIntervalMs = Math.max(60, keepaliveIntervalSeconds) * 1000;
    var userWasActive = false;
    var sessionExpiredShown = false;

    function markActive() {
        userWasActive = true;
    }

    function createSessionWarning() {
        var existing = document.getElementById("session-expired-warning");
        if (existing) {
            return existing;
        }

        var warning = document.createElement("div");
        warning.id = "session-expired-warning";
        warning.setAttribute("role", "alert");
        warning.style.position = "fixed";
        warning.style.left = "16px";
        warning.style.right = "16px";
        warning.style.bottom = "16px";
        warning.style.zIndex = "9999";
        warning.style.padding = "14px 16px";
        warning.style.border = "1px solid #f5c2c7";
        warning.style.borderRadius = "8px";
        warning.style.background = "#f8d7da";
        warning.style.color = "#842029";
        warning.style.boxShadow = "0 4px 18px rgba(0, 0, 0, 0.18)";
        warning.style.fontSize = "14px";
        warning.style.lineHeight = "1.4";
        warning.style.display = "none";
        warning.innerHTML = [
            "<strong>Сессия истекла.</strong> ",
            "Введённые данные остаются на этой странице. ",
            "Откройте <a href=\"/login\" target=\"_blank\" rel=\"noopener noreferrer\">страницу входа</a> ",
            "в новой вкладке, войдите снова, затем вернитесь сюда и нажмите «Сохранить»."
        ].join("");

        document.body.appendChild(warning);
        return warning;
    }

    function showSessionExpiredWarning() {
        sessionExpiredShown = true;
        createSessionWarning().style.display = "block";
    }

    function hideSessionExpiredWarning() {
        var warning = document.getElementById("session-expired-warning");
        if (warning) {
            warning.style.display = "none";
        }
        sessionExpiredShown = false;
    }

    async function fetchSession(url, options) {
        var response = await fetch(url, Object.assign({
            credentials: "same-origin",
            headers: {
                "Accept": "application/json",
                "X-Requested-With": "XMLHttpRequest"
            }
        }, options || {}));

        if (response.status === 401) {
            showSessionExpiredWarning();
            return false;
        }

        if (!response.ok) {
            return false;
        }

        hideSessionExpiredWarning();
        return true;
    }

    async function keepaliveIfNeeded() {
        if (!userWasActive || sessionExpiredShown) {
            return;
        }

        userWasActive = false;
        try {
            await fetchSession("/auth/session/keepalive", { method: "POST" });
        } catch (error) {
            // Сетевые ошибки не должны ломать форму. При сохранении будет отдельная проверка.
            // eslint-disable-next-line no-console
            console.warn("Session keepalive failed", error);
        }
    }

    async function sessionIsActiveBeforeSubmit() {
        try {
            return await fetchSession("/auth/session/status", { method: "GET" });
        } catch (error) {
            showSessionExpiredWarning();
            return false;
        }
    }

    function protectFormsFromExpiredSession() {
        document.addEventListener("submit", async function (event) {
            var form = event.target;
            if (!form || form.dataset.skipSessionCheck === "true") {
                return;
            }

            event.preventDefault();

            var active = await sessionIsActiveBeforeSubmit();
            if (!active) {
                return;
            }

            // Отправляем форму нативно, чтобы не запускать повторно submit-listener.
            HTMLFormElement.prototype.submit.call(form);
        }, true);
    }

    function bindActivityEvents() {
        ["click", "keydown", "input", "change", "pointerdown", "scroll"].forEach(function (eventName) {
            document.addEventListener(eventName, markActive, { passive: true });
        });
    }

    function init() {
        bindActivityEvents();
        protectFormsFromExpiredSession();
        window.setInterval(keepaliveIfNeeded, checkIntervalMs);
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", init);
    } else {
        init();
    }
})();
