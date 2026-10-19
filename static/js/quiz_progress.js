document.addEventListener("DOMContentLoaded", function () {
    document.querySelectorAll("[data-quiz-form]").forEach(function (form) {
        const status = form.querySelector("[data-answered-status]");
        const fieldsets = Array.from(form.querySelectorAll("fieldset.quiz-question"));
        if (!status || !fieldsets.length) { return; }

        function isAnswered(fieldset) {
            const checked = fieldset.querySelector("input[type=radio]:checked");
            if (checked) { return true; }
            const text = fieldset.querySelector("input[type=text], textarea");
            if (text && text.value.trim()) { return true; }
            return Array.from(fieldset.querySelectorAll("select")).some(function (select) { return select.value; });
        }

        function update() {
            const answered = fieldsets.filter(isAnswered).length;
            status.textContent = answered + " of " + fieldsets.length + " answered";
            return answered;
        }

        form.addEventListener("input", update);
        form.addEventListener("change", update);
        form.addEventListener("reset", function () { window.setTimeout(update, 0); });
        form.addEventListener("submit", function (event) {
            const timed = form.querySelector(".mock-exam-timer");
            const missing = fieldsets.length - update();
            if (missing > 0 && !(timed && form.dataset.autosubmit)) {
                const noun = missing === 1 ? "question" : "questions";
                if (!window.confirm(missing + " " + noun + " unanswered. Submit anyway?")) {
                    event.preventDefault();
                }
            }
        });
    });
});
