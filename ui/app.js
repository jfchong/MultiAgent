/* Work Release Dashboard — vanilla JS */
(function () {
    "use strict";

    const API = "";
    let refreshTimer = null;
    const REFRESH_INTERVAL = 5000;
    let currentFilter = "pending";

    // ---- Helpers ----

    async function api(method, path, body) {
        const opts = { method, headers: {} };
        if (body) {
            opts.headers["Content-Type"] = "application/json";
            opts.body = JSON.stringify(body);
        }
        const res = await fetch(API + path, opts);
        return res.json();
    }

    function $(sel) { return document.querySelector(sel); }
    function $$(sel) { return document.querySelectorAll(sel); }

    function timeAgo(iso) {
        if (!iso) return "-";
        const diff = (Date.now() - new Date(iso).getTime()) / 1000;
        if (diff < 60) return Math.floor(diff) + "s ago";
        if (diff < 3600) return Math.floor(diff / 60) + "m ago";
        if (diff < 86400) return Math.floor(diff / 3600) + "h ago";
        return Math.floor(diff / 86400) + "d ago";
    }

    function escHtml(str) {
        if (!str) return "";
        const d = document.createElement("div");
        d.textContent = str;
        return d.innerHTML;
    }

    // ---- Toast Notifications ----

    function toast(message, type) {
        type = type || "info";
        let toastContainer = $("#toast-container");
        if (!toastContainer) {
            toastContainer = document.createElement("div");
            toastContainer.id = "toast-container";
            toastContainer.style.cssText = [
                "position:fixed",
                "bottom:1.5rem",
                "right:1.5rem",
                "display:flex",
                "flex-direction:column",
                "gap:0.5rem",
                "z-index:9999",
            ].join(";");
            document.body.appendChild(toastContainer);
        }

        const el = document.createElement("div");
        el.className = "toast toast-" + type;
        el.textContent = message;
        el.style.cssText = [
            "background:" + (type === "success" ? "#22c55e" : type === "error" ? "#ef4444" : "#3b82f6"),
            "color:#fff",
            "padding:0.6rem 1rem",
            "border-radius:6px",
            "font-size:0.875rem",
            "box-shadow:0 2px 8px rgba(0,0,0,0.3)",
            "opacity:1",
            "transition:opacity 0.4s ease",
        ].join(";");
        toastContainer.appendChild(el);

        setTimeout(function () {
            el.style.opacity = "0";
            setTimeout(function () { el.remove(); }, 400);
        }, 3000);
    }

    // ---- Status Bar ----

    async function refreshStatus() {
        try {
            const s = await api("GET", "/api/status");
            $("#stat-running").textContent = s.running_agents;
            $("#stat-pending").textContent = s.pending_releases;
            if ($("#stat-queue")) $("#stat-queue").textContent = s.queue_depth;
            $("#stat-rules").textContent = s.active_rules;
            $("#stat-approved").textContent = s.total_approved;
            $("#stat-rejected").textContent = s.total_rejected;
            $("#stat-auto").textContent = s.total_auto_released;
        } catch (e) {
            console.error("Status fetch failed:", e);
        }
    }

    // ---- Releases ----

    function groupByLevel(releases) {
        const groups = {};
        for (const r of releases) {
            const lvl = r.agent_level;
            if (!groups[lvl]) groups[lvl] = [];
            groups[lvl].push(r);
        }
        return groups;
    }

    const LEVEL_NAMES = {
        0: "L0 — Director",
        1: "L1 — Agents",
        2: "L2 — Sub-Agents",
        3: "L3 — Workers",
    };

    function renderReleases(releases) {
        const container = $("#releases-container");

        if (!releases.length) {
            container.innerHTML = '<div class="empty-state">No ' + escHtml(currentFilter || "matching") + " releases found.</div>";
            return;
        }

        const groups = groupByLevel(releases);
        let html = "";

        for (const level of [0, 1, 2, 3]) {
            const items = groups[level];
            if (!items || !items.length) continue;

            html += '<div class="level-group">';
            html += "<h3>" + escHtml(LEVEL_NAMES[level] || "Level " + level) + " (" + items.length + ")</h3>";
            html += '<table class="releases-table"><thead><tr>';
            html += "<th>Title</th><th>Agent</th><th>Action</th><th>Input</th><th>Status</th><th>Created</th><th>Actions</th>";
            html += "</tr></thead><tbody>";

            for (const r of items) {
                html += "<tr>";
                html += "<td>" + escHtml(r.title) + "</td>";
                html += '<td>' + escHtml(r.agent_name || r.agent_id) + ' <span class="badge badge-level">L' + r.agent_level + "</span></td>";
                html += '<td><span class="badge badge-action">' + escHtml(r.action_type) + "</span></td>";
                html += '<td><span class="preview-text" title="' + escHtml(r.input_preview) + '">' + escHtml(r.input_preview) + "</span></td>";
                html += '<td><span class="badge badge-' + escHtml(r.status) + '">' + escHtml(r.status) + "</span></td>";
                html += "<td>" + timeAgo(r.created_at) + "</td>";
                html += '<td class="actions-cell">';

                if (r.status === "pending") {
                    html += '<button class="btn btn-approve" data-id="' + r.release_id + '" data-action="approve">Approve</button>';
                    html += '<button class="btn btn-reject" data-id="' + r.release_id + '" data-action="reject">Reject</button>';
                    html += '<button class="btn btn-auto" data-id="' + r.release_id + '" data-action="auto-release" title="Approve + create auto-release rule">Auto</button>';
                }

                html += "</td></tr>";
            }

            html += "</tbody></table></div>";
        }

        container.innerHTML = html;

        // Delegated click handlers for action buttons
        container.querySelectorAll(".btn[data-action]").forEach(function (btn) {
            btn.addEventListener("click", function () {
                handleAction(btn.dataset.id, btn.dataset.action);
            });
        });
    }

    async function loadReleases() {
        const query = currentFilter ? "?status=" + encodeURIComponent(currentFilter) : "";
        try {
            const releases = await api("GET", "/api/releases" + query);
            renderReleases(releases);
            $("#last-updated").textContent = "Updated " + new Date().toLocaleTimeString();
        } catch (e) {
            $("#releases-container").innerHTML = '<div class="empty-state">Failed to load releases. Is the server running?</div>';
        }
    }

    async function handleAction(releaseId, action) {
        try {
            await api("POST", "/api/releases/" + releaseId + "/" + action);
            const actionLabels = {
                approve: "approved",
                reject: "rejected",
                "auto-release": "auto-released",
            };
            toast("Release " + (actionLabels[action] || action) + ".", "success");
            await Promise.all([loadReleases(), refreshStatus()]);
        } catch (e) {
            console.error("Action failed:", e);
            toast("Action failed: " + action, "error");
        }
    }

    // ---- Batch Operations ----

    async function approveAll() {
        const btns = $$("#releases-container .btn-approve");
        if (!btns.length) {
            toast("No pending releases to approve.", "info");
            return;
        }
        if (!confirm("Approve all " + btns.length + " pending releases?")) return;

        const ids = Array.from(btns).map(function (b) { return b.dataset.id; });
        let approved = 0;
        for (const id of ids) {
            try {
                await api("POST", "/api/releases/" + id + "/approve");
                approved++;
            } catch (e) {
                console.error("Failed to approve release " + id, e);
            }
        }
        toast("Approved " + approved + " of " + ids.length + " releases.", approved === ids.length ? "success" : "error");
        await Promise.all([loadReleases(), refreshStatus()]);
    }

    // ---- Auto-Release Rules ----

    async function loadRules() {
        try {
            const rules = await api("GET", "/api/rules");
            const tbody = $("#rules-tbody");
            const empty = $("#rules-empty");

            if (!rules.length) {
                tbody.innerHTML = "";
                empty.style.display = "block";
                return;
            }

            empty.style.display = "none";
            let html = "";
            for (const rule of rules) {
                html += "<tr>";
                html += "<td>" + escHtml(rule.match_agent_type) + "</td>";
                html += "<td>" + escHtml(rule.match_action_type) + "</td>";
                html += "<td>" + escHtml(rule.match_title_pattern || "*") + "</td>";
                html += "<td>" + rule.fire_count + "</td>";
                html += "<td>" + timeAgo(rule.created_at) + "</td>";
                html += '<td><button class="btn btn-delete" data-rule-id="' + rule.rule_id + '">Delete</button></td>';
                html += "</tr>";
            }
            tbody.innerHTML = html;

            tbody.querySelectorAll(".btn-delete").forEach(function (btn) {
                btn.addEventListener("click", function () {
                    deleteRule(btn.dataset.ruleId);
                });
            });
        } catch (e) {
            console.error("Rules fetch failed:", e);
            toast("Failed to load auto-release rules.", "error");
        }
    }

    async function deleteRule(ruleId) {
        if (!confirm("Delete this auto-release rule?")) return;
        try {
            await api("DELETE", "/api/rules/" + ruleId);
            toast("Rule deleted.", "success");
            await Promise.all([loadRules(), refreshStatus()]);
        } catch (e) {
            console.error("Delete rule failed:", e);
            toast("Failed to delete rule.", "error");
        }
    }

    // ---- Auto-Refresh ----

    function startRefresh() {
        stopRefresh();
        refreshTimer = setInterval(function () {
            loadReleases();
            refreshStatus();
        }, REFRESH_INTERVAL);
    }

    function stopRefresh() {
        if (refreshTimer) {
            clearInterval(refreshTimer);
            refreshTimer = null;
        }
    }

    // ---- Filter Buttons ----

    function setActiveFilter(status) {
        currentFilter = status;
        $$("#filter-buttons .filter-btn").forEach(function (btn) {
            if (btn.dataset.status === status) {
                btn.classList.add("active");
            } else {
                btn.classList.remove("active");
            }
        });
    }

    // ---- Init ----

    function init() {
        // Filter button click handlers
        $$("#filter-buttons .filter-btn").forEach(function (btn) {
            btn.addEventListener("click", function () {
                setActiveFilter(btn.dataset.status);
                loadReleases();
            });
        });

        // Set default active filter to 'pending'
        setActiveFilter(currentFilter);

        // Auto-refresh toggle
        $("#auto-refresh").addEventListener("change", function () {
            if (this.checked) {
                startRefresh();
            } else {
                stopRefresh();
            }
        });

        // Batch approve
        $("#btn-approve-all").addEventListener("click", approveAll);

        // Rules toggle — uses the HTML `hidden` attribute
        $("#rules-toggle").addEventListener("click", function () {
            const body = $("#rules-body");
            const icon = $("#rules-toggle-icon");
            const toggleBtn = $("#rules-toggle-btn");
            const isHidden = body.hasAttribute("hidden");

            if (isHidden) {
                body.removeAttribute("hidden");
                icon.classList.add("open");
                if (toggleBtn) toggleBtn.setAttribute("aria-expanded", "true");
                loadRules();
            } else {
                body.setAttribute("hidden", "");
                icon.classList.remove("open");
                if (toggleBtn) toggleBtn.setAttribute("aria-expanded", "false");
            }
        });

        // Initial load
        refreshStatus();
        loadReleases();
        startRefresh();
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", init);
    } else {
        init();
    }
})();
