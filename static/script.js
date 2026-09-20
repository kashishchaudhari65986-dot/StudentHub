(() => {
    const csrfToken = document.querySelector('meta[name="csrf-token"]')?.content || "";
    const assignmentPage = document.querySelector("[data-assignment-page]");
    if (assignmentPage) {
        const list = assignmentPage.querySelector("[data-assignment-list]");
        const emptyState = assignmentPage.querySelector("[data-assignment-empty]");
        const form = assignmentPage.querySelector("[data-assignment-form]");
        const message = assignmentPage.querySelector("[data-assignment-message]");

        function showMessage(text, isError = false) {
            if (!message) return;
            message.textContent = text;
            message.className = `form-message${isError ? " form-message-error" : ""}`;
        }

        async function apiRequest(url, options = {}) {
            const response = await fetch(url, {
                ...options,
                headers: { "Content-Type": "application/json", "X-CSRFToken": csrfToken, ...(options.headers || {}) },
            });
            const body = await response.json().catch(() => ({}));
            if (!response.ok) {
                throw new Error(body.error || "The request could not be completed.");
            }
            return body;
        }

        function assignmentData(card) {
            return {
                title: card.querySelector("[name='title']").value.trim(),
                description: card.querySelector("[name='description']").value.trim(),
                subject: card.querySelector("[name='subject']").value.trim(),
                due_date: card.querySelector("[name='due_date']").value,
                status: card.querySelector("[name='status']").value,
            };
        }

        function renderAssignments(assignments) {
            let assignmentList = assignmentPage.querySelector("[data-assignment-list]");
            if (!assignments.length) {
                if (assignmentList) {
                    assignmentList.remove();
                }
                if (emptyState) {
                    emptyState.hidden = false;
                }
                return;
            }
            if (emptyState) {
                emptyState.hidden = true;
            }
            if (!assignmentList) {
                assignmentList = document.createElement("div");
                assignmentList.className = "assignment-list";
                assignmentList.dataset.assignmentList = "";
                assignmentPage.querySelector(".container").append(assignmentList);
            }
            assignmentList.replaceChildren(...assignments.map(createAssignmentCard));
        }

        function createAssignmentCard(assignment) {
            const card = document.createElement("article");
            card.className = "assignment-card";
            card.dataset.assignmentId = assignment.id;

            const title = document.createElement("h2");
            title.textContent = assignment.title;
            const meta = document.createElement("p");
            meta.className = "assignment-meta";
            meta.textContent = `${assignment.subject} | Due ${assignment.due_date}`;
            const status = document.createElement("span");
            status.className = "status-badge";
            status.textContent = assignment.status;
            meta.append(" ", status);
            card.append(title, meta);

            if (assignment.description) {
                const description = document.createElement("p");
                description.className = "assignment-description";
                description.textContent = assignment.description;
                card.append(description);
            }

            const actions = document.createElement("div");
            actions.className = "assignment-actions";
            const editButton = document.createElement("button");
            editButton.className = "button button-secondary";
            editButton.type = "button";
            editButton.textContent = "Edit";
            editButton.addEventListener("click", () => showEditForm(card, assignment));
            const deleteButton = document.createElement("button");
            deleteButton.className = "button button-secondary";
            deleteButton.type = "button";
            deleteButton.textContent = "Delete";
            deleteButton.addEventListener("click", async () => {
                try {
                    await apiRequest(`/api/assignments/${assignment.id}`, { method: "DELETE" });
                    await loadAssignments();
                    showMessage("Assignment deleted.");
                } catch (error) {
                    showMessage(error.message, true);
                }
            });
            actions.append(editButton, deleteButton);
            card.append(actions);
            return card;
        }

        function showEditForm(card, assignment) {
            card.replaceChildren();
            const editForm = document.createElement("form");
            editForm.className = "auth-form";
            editForm.innerHTML = `
                <label>Title <input name="title" required></label>
                <label>Description <textarea name="description"></textarea></label>
                <label>Subject <input name="subject" required></label>
                <label>Due date <input name="due_date" type="date" required></label>
                <label>Status <select name="status"><option>Pending</option><option>Completed</option></select></label>
                <button class="button button-primary" type="submit">Save changes</button>
                <button class="button button-secondary" type="button">Cancel</button>
            `;
            editForm.elements.title.value = assignment.title;
            editForm.elements.description.value = assignment.description;
            editForm.elements.subject.value = assignment.subject;
            editForm.elements.due_date.value = assignment.due_date;
            editForm.elements.status.value = assignment.status;
            editForm.querySelector("button[type='button']").addEventListener("click", () => loadAssignments());
            editForm.addEventListener("submit", async (event) => {
                event.preventDefault();
                try {
                    await apiRequest(`/api/assignments/${assignment.id}`, {
                        method: "PUT",
                        body: JSON.stringify(assignmentData(editForm)),
                    });
                    await loadAssignments();
                    showMessage("Assignment updated.");
                } catch (error) {
                    showMessage(error.message, true);
                }
            });
            card.append(editForm);
        }

        async function loadAssignments() {
            const data = await apiRequest("/api/assignments");
            renderAssignments(data.assignments);
        }

        if (form) {
            form.addEventListener("submit", async (event) => {
                event.preventDefault();
                const payload = Object.fromEntries(new FormData(form));
                try {
                    await apiRequest("/api/assignments", {
                        method: "POST",
                        body: JSON.stringify(payload),
                    });
                    form.reset();
                    await loadAssignments();
                    showMessage("Assignment created.");
                } catch (error) {
                    showMessage(error.message, true);
                }
            });
        }

        loadAssignments().catch((error) => showMessage(error.message, true));
    }

    const notePage = document.querySelector("[data-note-page]");
    if (notePage) {
        const list = notePage.querySelector("[data-note-list]");
        const form = notePage.querySelector("[data-note-form]");
        const emptyState = notePage.querySelector("[data-note-empty]");
        const message = notePage.querySelector("[data-note-message]");

        function showMessage(text, isError = false) {
            if (!message) return;
            message.textContent = text;
            message.className = `form-message${isError ? " form-message-error" : ""}`;
        }

        async function apiRequest(url, options = {}) {
            const response = await fetch(url, {
                ...options,
                headers: { "Content-Type": "application/json", "X-CSRFToken": csrfToken, ...(options.headers || {}) },
            });
            const body = await response.json().catch(() => ({}));
            if (!response.ok) {
                throw new Error(body.error || "The request could not be completed.");
            }
            return body;
        }

        function renderNotes(notes) {
            let noteList = notePage.querySelector("[data-note-list]");
            if (!noteList) {
                noteList = document.createElement("div");
                noteList.className = "assignment-list";
                noteList.dataset.noteList = "";
                notePage.querySelector(".container").append(noteList);
            }
            if (!notes.length) {
                noteList.replaceChildren();
                if (emptyState) {
                    emptyState.hidden = false;
                }
                return;
            }
            if (emptyState) {
                emptyState.hidden = true;
            }
            noteList.replaceChildren(...notes.map(createNoteCard));
        }

        function createNoteCard(note) {
            const card = document.createElement("article");
            card.className = "note-card";
            card.dataset.noteId = note.id;
            card.dataset.noteCard = "";
            card.dataset.noteTitle = note.title;
            card.dataset.noteSubject = note.subject;
            card.dataset.noteContent = note.content;

            const title = document.createElement("h2");
            title.textContent = note.title;
            const meta = document.createElement("p");
            meta.className = "assignment-meta";
            const subject = document.createElement("span");
            subject.textContent = note.subject;
            const date = document.createElement("span");
            date.className = "note-date";
            date.textContent = new Date(note.created_at).toLocaleString();
            meta.append(subject, date);
            const content = document.createElement("p");
            content.className = "note-preview";
            content.textContent = note.content;

            const actions = document.createElement("div");
            actions.className = "assignment-actions";
            const editButton = document.createElement("button");
            editButton.type = "button";
            editButton.className = "button button-secondary";
            editButton.textContent = "Edit";
            editButton.addEventListener("click", () => showEditForm(card, note));
            const deleteButton = document.createElement("button");
            deleteButton.type = "button";
            deleteButton.className = "button button-secondary";
            deleteButton.textContent = "Delete";
            deleteButton.addEventListener("click", async () => {
                try {
                    await apiRequest(`/api/notes/${note.id}`, { method: "DELETE" });
                    await loadNotes();
                    showMessage("Note deleted.");
                } catch (error) {
                    showMessage(error.message, true);
                }
            });
            actions.append(editButton, deleteButton);
            card.append(title, meta, content, actions);
            return card;
        }

        function showEditForm(card, note) {
            card.replaceChildren();
            const editForm = document.createElement("form");
            editForm.className = "auth-form";
            editForm.innerHTML = `
                <label>Title <input name="title" required></label>
                <label>Subject <input name="subject" required></label>
                <label>Content <textarea name="content" required></textarea></label>
                <button class="button button-primary" type="submit">Save changes</button>
                <button class="button button-secondary" type="button">Cancel</button>
            `;
            editForm.elements.title.value = note.title;
            editForm.elements.subject.value = note.subject;
            editForm.elements.content.value = note.content;
            editForm.querySelector("button[type='button']").addEventListener("click", () => loadNotes());
            editForm.addEventListener("submit", async (event) => {
                event.preventDefault();
                try {
                    await apiRequest(`/api/notes/${note.id}`, {
                        method: "PUT",
                        body: JSON.stringify({
                            title: editForm.elements.title.value.trim(),
                            subject: editForm.elements.subject.value.trim(),
                            content: editForm.elements.content.value.trim(),
                        }),
                    });
                    await loadNotes();
                    showMessage("Note updated.");
                } catch (error) {
                    showMessage(error.message, true);
                }
            });
            card.append(editForm);
        }

        async function loadNotes() {
            const data = await apiRequest("/api/notes");
            renderNotes(data.notes || []);
        }

        if (form) {
            form.addEventListener("submit", async (event) => {
                event.preventDefault();
                try {
                    await apiRequest("/api/notes", {
                        method: "POST",
                        body: JSON.stringify({
                            title: form.elements.title.value.trim(),
                            subject: form.elements.subject.value.trim(),
                            content: form.elements.content.value.trim(),
                        }),
                    });
                    form.reset();
                    await loadNotes();
                    showMessage("Note created.");
                } catch (error) {
                    showMessage(error.message, true);
                }
            });
        }

        loadNotes().catch((error) => showMessage(error.message, true));
    }

    const taskPage = document.querySelector("[data-task-page]");
    if (taskPage) {
        const list = taskPage.querySelector("[data-task-list]");
        const form = taskPage.querySelector("[data-task-form]");
        const emptyState = taskPage.querySelector("[data-task-empty]");
        const message = taskPage.querySelector("[data-task-message]");

        function showMessage(text, isError = false) {
            if (!message) return;
            message.textContent = text;
            message.className = `form-message${isError ? " form-message-error" : ""}`;
        }

        async function apiRequest(url, options = {}) {
            const response = await fetch(url, {
                ...options,
                headers: { "Content-Type": "application/json", "X-CSRFToken": csrfToken, ...(options.headers || {}) },
            });
            const body = await response.json().catch(() => ({}));
            if (!response.ok) {
                throw new Error(body.error || "The request could not be completed.");
            }
            return body;
        }

        function renderTasks(tasks) {
            let taskList = taskPage.querySelector("[data-task-list]");
            if (!taskList) {
                taskList = document.createElement("div");
                taskList.className = "assignment-list";
                taskList.dataset.taskList = "";
                taskPage.querySelector(".container").append(taskList);
            }
            if (!tasks.length) {
                taskList.replaceChildren();
                if (emptyState) {
                    emptyState.hidden = false;
                }
                return;
            }
            if (emptyState) {
                emptyState.hidden = true;
            }
            taskList.replaceChildren(...tasks.map(createTaskCard));
        }

        function createTaskCard(task) {
            const card = document.createElement("article");
            card.className = `task-card${task.completed ? " task-completed" : ""}`;
            card.dataset.taskId = task.id;
            card.dataset.taskCard = "";
            card.dataset.taskTitle = task.title;
            card.dataset.taskCompleted = String(task.completed);

            const title = document.createElement("h2");
            title.textContent = task.title;
            const meta = document.createElement("p");
            meta.className = "assignment-meta";
            const dueDate = document.createElement("span");
            dueDate.textContent = `Due ${task.due_date}`;
            const taskStatus = document.createElement("span");
            taskStatus.className = `task-status ${task.completed ? "task-status-complete" : "task-status-pending"}`;
            taskStatus.textContent = task.completed ? "Completed" : "Incomplete";
            meta.append(dueDate, taskStatus);
            const description = document.createElement("p");
            description.className = "task-description";
            description.textContent = task.description || "No description.";

            const actions = document.createElement("div");
            actions.className = "assignment-actions";
            const editButton = document.createElement("button");
            editButton.type = "button";
            editButton.className = "button button-secondary";
            editButton.textContent = "Edit";
            editButton.addEventListener("click", () => showEditForm(card, task));
            const toggleButton = document.createElement("button");
            toggleButton.type = "button";
            toggleButton.className = "button button-secondary";
            toggleButton.textContent = task.completed ? "Mark incomplete" : "Mark complete";
            toggleButton.addEventListener("click", async () => {
                try {
                    await apiRequest(`/api/tasks/${task.id}/toggle`, { method: "POST" });
                    await loadTasks();
                    showMessage(task.completed ? "Task marked incomplete." : "Task marked complete.");
                } catch (error) {
                    showMessage(error.message, true);
                }
            });
            const deleteButton = document.createElement("button");
            deleteButton.type = "button";
            deleteButton.className = "button button-secondary";
            deleteButton.textContent = "Delete";
            deleteButton.addEventListener("click", async () => {
                try {
                    await apiRequest(`/api/tasks/${task.id}`, { method: "DELETE" });
                    await loadTasks();
                    showMessage("Task deleted.");
                } catch (error) {
                    showMessage(error.message, true);
                }
            });
            actions.append(editButton, toggleButton, deleteButton);
            card.append(title, meta, description, actions);
            return card;
        }

        function showEditForm(card, task) {
            card.replaceChildren();
            const editForm = document.createElement("form");
            editForm.className = "auth-form";
            editForm.innerHTML = `
                <label>Title <input name="title" required></label>
                <label>Description <textarea name="description"></textarea></label>
                <label>Due date <input name="due_date" type="date" required></label>
                <button class="button button-primary" type="submit">Save changes</button>
                <button class="button button-secondary" type="button">Cancel</button>
            `;
            editForm.elements.title.value = task.title;
            editForm.elements.description.value = task.description || "";
            editForm.elements.due_date.value = task.due_date;
            editForm.querySelector("button[type='button']").addEventListener("click", () => loadTasks());
            editForm.addEventListener("submit", async (event) => {
                event.preventDefault();
                try {
                    await apiRequest(`/api/tasks/${task.id}`, {
                        method: "PUT",
                        body: JSON.stringify({
                            title: editForm.elements.title.value.trim(),
                            description: editForm.elements.description.value.trim(),
                            due_date: editForm.elements.due_date.value,
                        }),
                    });
                    await loadTasks();
                    showMessage("Task updated.");
                } catch (error) {
                    showMessage(error.message, true);
                }
            });
            card.append(editForm);
        }

        async function loadTasks() {
            const data = await apiRequest("/api/tasks");
            renderTasks(data.tasks || []);
        }

        if (form) {
            form.addEventListener("submit", async (event) => {
                event.preventDefault();
                try {
                    await apiRequest("/api/tasks", {
                        method: "POST",
                        body: JSON.stringify({
                            title: form.elements.title.value.trim(),
                            description: form.elements.description.value.trim(),
                            due_date: form.elements.due_date.value,
                        }),
                    });
                    form.reset();
                    await loadTasks();
                    showMessage("Task created.");
                } catch (error) {
                    showMessage(error.message, true);
                }
            });
        }

        loadTasks().catch((error) => showMessage(error.message, true));
    }
})();

(() => {
    const dashboardPage = document.querySelector("[data-dashboard-page]");
    if (dashboardPage) {
        const statMap = {
            assignments: dashboardPage.querySelector('[data-stat="assignments"]'),
            pending_assignments: dashboardPage.querySelector('[data-stat="pending_assignments"]'),
            completed_assignments: dashboardPage.querySelector('[data-stat="completed_assignments"]'),
            notes: dashboardPage.querySelector('[data-stat="notes"]'),
            tasks: dashboardPage.querySelector('[data-stat="tasks"]'),
            completed_tasks: dashboardPage.querySelector('[data-stat="completed_tasks"]'),
            pending_tasks: dashboardPage.querySelector('[data-stat="pending_tasks"]'),
        };
        const recentAssignments = dashboardPage.querySelector("[data-dashboard-recent-assignments]");
        const recentTasks = dashboardPage.querySelector("[data-dashboard-recent-tasks]");
        const errorBox = dashboardPage.querySelector("[data-dashboard-error]");
        const emptyAssignments = dashboardPage.querySelector("[data-dashboard-empty-assignments]");
        const emptyTasks = dashboardPage.querySelector("[data-dashboard-empty-tasks]");

        function showError(message) {
            if (!errorBox) return;
            errorBox.hidden = false;
            errorBox.textContent = message;
            errorBox.className = "form-message form-message-error";
        }

        function clearError() {
            if (!errorBox) return;
            errorBox.hidden = true;
            errorBox.textContent = "";
            errorBox.className = "form-message";
        }

        function setStats(stats) {
            Object.entries(statMap).forEach(([key, element]) => {
                if (!element) return;
                const value = stats[key] ?? 0;
                element.textContent = value;
            });
        }

        function renderRecentAssignments(items) {
            if (!recentAssignments) return;
            recentAssignments.textContent = "";
            if (!items.length) {
                if (emptyAssignments) emptyAssignments.hidden = false;
                return;
            }
            if (emptyAssignments) emptyAssignments.hidden = true;
            const list = document.createElement("div");
            list.className = "assignment-list";
            list.style.gridTemplateColumns = "1fr";
            list.style.gap = "0.8rem";
            items.forEach((item) => {
                const wrap = document.createElement("div");
                wrap.className = "assignment-card";
                wrap.style.padding = "1rem";
                wrap.innerHTML = `
                    <h2 style="font-size: 1.05rem; margin-bottom: 0.4rem;">${item.title}</h2>
                    <p class="assignment-meta">
                        <span>${item.subject}</span>
                        <span>Due ${item.due_date}</span>
                        <span class="status-badge">${item.status}</span>
                    </p>
                `;
                list.appendChild(wrap);
            });
            recentAssignments.appendChild(list);
        }

        function renderRecentTasks(items) {
            if (!recentTasks) return;
            recentTasks.textContent = "";
            if (!items.length) {
                if (emptyTasks) emptyTasks.hidden = false;
                return;
            }
            if (emptyTasks) emptyTasks.hidden = true;
            const list = document.createElement("div");
            list.className = "assignment-list";
            list.style.gridTemplateColumns = "1fr";
            list.style.gap = "0.8rem";
            items.forEach((item) => {
                const wrap = document.createElement("div");
                wrap.className = "task-card";
                wrap.style.padding = "1rem";
                wrap.innerHTML = `
                    <h2 style="font-size: 1.05rem; margin-bottom: 0.4rem;">${item.title}</h2>
                    <p class="assignment-meta">
                        <span>Due ${item.due_date}</span>
                        <span class="task-status ${item.completed ? "task-status-complete" : "task-status-pending"}">${item.completed ? "Completed" : "Pending"}</span>
                    </p>
                `;
                list.appendChild(wrap);
            });
            recentTasks.appendChild(list);
        }

        async function loadDashboardStats() {
            clearError();
            const response = await fetch("/api/dashboard/stats", { method: "GET", headers: { Accept: "application/json" } });
            let data = {};
            try {
                data = await response.json();
            } catch (error) {
                throw new Error("The dashboard statistics could not be loaded.");
            }
            if (!response.ok) {
                if (response.status === 401) {
                    throw new Error("Please sign in to view your dashboard.");
                }
                throw new Error(data.error || "The dashboard statistics could not be loaded.");
            }
            setStats(data);
        }

        async function loadRecentAssignments() {
            const response = await fetch("/api/dashboard/recent-assignments", { method: "GET", headers: { Accept: "application/json" } });
            let data = [];
            try {
                data = await response.json();
            } catch (error) {
                throw new Error("Recent assignments could not be loaded.");
            }
            if (!response.ok) {
                if (response.status === 401) {
                    throw new Error("Please sign in to view recent assignments.");
                }
                throw new Error(data.error || "Recent assignments could not be loaded.");
            }
            renderRecentAssignments(Array.isArray(data) ? data : []);
        }

        async function loadRecentTasks() {
            const response = await fetch("/api/dashboard/recent-tasks", { method: "GET", headers: { Accept: "application/json" } });
            let data = [];
            try {
                data = await response.json();
            } catch (error) {
                throw new Error("Recent tasks could not be loaded.");
            }
            if (!response.ok) {
                if (response.status === 401) {
                    throw new Error("Please sign in to view recent tasks.");
                }
                throw new Error(data.error || "Recent tasks could not be loaded.");
            }
            renderRecentTasks(Array.isArray(data) ? data : []);
        }

        Promise.all([loadDashboardStats(), loadRecentAssignments(), loadRecentTasks()])
            .catch((error) => {
                showError(error.message || "The dashboard could not load. Please try again.");
            });
    }

    const assignmentSearch = document.querySelector("[data-assignment-search]");
    if (assignmentSearch) {
        const statusFilter = document.querySelector("[data-assignment-status-filter]");
        const emptyState = document.querySelector("[data-assignment-empty]");

        function applyAssignmentFilters() {
            const query = (assignmentSearch.value || "").trim().toLowerCase();
            const status = statusFilter ? statusFilter.value : "All";
            const cards = Array.from(document.querySelectorAll("[data-assignment-card]"));
            let visibleCount = 0;

            cards.forEach((card) => {
                const title = (card.dataset.assignmentTitle || "").toLowerCase();
                const subject = (card.dataset.assignmentSubject || "").toLowerCase();
                const cardStatus = (card.dataset.assignmentStatus || "").trim();
                const matchesSearch = !query || title.includes(query) || subject.includes(query);
                const matchesStatus = status === "All" || cardStatus === status;
                const show = matchesSearch && matchesStatus;
                card.hidden = !show;
                if (show) visibleCount += 1;
            });

            if (emptyState) {
                emptyState.hidden = visibleCount !== 0;
            }
        }

        assignmentSearch.addEventListener("input", applyAssignmentFilters);
        if (statusFilter) {
            statusFilter.addEventListener("change", applyAssignmentFilters);
        }
        applyAssignmentFilters();
    }

    const noteSearch = document.querySelector("[data-note-search]");
    if (noteSearch) {
        const emptyState = document.querySelector("[data-note-empty]");

        function applyNoteFilters() {
            const query = (noteSearch.value || "").trim().toLowerCase();
            const cards = Array.from(document.querySelectorAll("[data-note-card]"));
            let visibleCount = 0;

            cards.forEach((card) => {
                const title = (card.dataset.noteTitle || "").toLowerCase();
                const subject = (card.dataset.noteSubject || "").toLowerCase();
                const content = (card.dataset.noteContent || "").toLowerCase();
                const show = !query || title.includes(query) || subject.includes(query) || content.includes(query);
                card.hidden = !show;
                if (show) visibleCount += 1;
            });

            if (emptyState) {
                emptyState.hidden = visibleCount !== 0;
            }
        }

        noteSearch.addEventListener("input", applyNoteFilters);
        applyNoteFilters();
    }

    const taskSearch = document.querySelector("[data-task-search]");
    if (taskSearch) {
        const statusFilter = document.querySelector("[data-task-status-filter]");
        const emptyState = document.querySelector("[data-task-empty]");

        function applyTaskFilters() {
            const query = (taskSearch.value || "").trim().toLowerCase();
            const status = statusFilter ? statusFilter.value : "All";
            const cards = Array.from(document.querySelectorAll("[data-task-card]"));
            let visibleCount = 0;

            cards.forEach((card) => {
                const title = (card.dataset.taskTitle || "").toLowerCase();
                const completed = String(card.dataset.taskCompleted || "false") === "true";
                const matchesSearch = !query || title.includes(query);
                const matchesStatus = status === "All" || (status === "Completed" && completed) || (status === "Pending" && !completed);
                const show = matchesSearch && matchesStatus;
                card.hidden = !show;
                if (show) visibleCount += 1;
            });

            if (emptyState) {
                emptyState.hidden = visibleCount !== 0;
            }
        }

        taskSearch.addEventListener("input", applyTaskFilters);
        if (statusFilter) {
            statusFilter.addEventListener("change", applyTaskFilters);
        }
        applyTaskFilters();
    }
})();
