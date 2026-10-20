/* Practice quizzes: show one question at a time with a progress bar and a question map.
   Without JS (or for timed mock exams) every question stays on the page. */
document.addEventListener("DOMContentLoaded", function () {
    document.querySelectorAll("form[data-stepper]").forEach(function (form) {
        var fieldsets = Array.prototype.slice.call(form.querySelectorAll("fieldset.quiz-question"));
        if (fieldsets.length < 2) { return; }
        var actions = form.querySelector(".quiz-actions");
        var current = 0;

        var top = document.createElement("div");
        top.className = "stepper-top";
        top.innerHTML = '<div class="stepper-bar" aria-hidden="true"><span></span></div>' +
            '<p class="stepper-label" role="status" aria-live="polite"></p>' +
            '<div class="stepper-map" role="group" aria-label="Question map"></div>';
        var first = fieldsets[0];
        first.parentNode.insertBefore(top, first);
        var bar = top.querySelector(".stepper-bar span");
        var label = top.querySelector(".stepper-label");
        var map = top.querySelector(".stepper-map");

        var nav = document.createElement("div");
        nav.className = "stepper-nav";
        nav.innerHTML = '<button type="button" class="stepper-back">Back</button>' +
            '<button type="button" class="stepper-next">Next question</button>';
        fieldsets[fieldsets.length - 1].after(nav);
        var back = nav.querySelector(".stepper-back");
        var next = nav.querySelector(".stepper-next");

        var dots = fieldsets.map(function (_, i) {
            var b = document.createElement("button");
            b.type = "button";
            b.className = "stepper-dot";
            b.textContent = i + 1;
            b.setAttribute("aria-label", "Go to question " + (i + 1));
            b.addEventListener("click", function () { show(i); });
            map.appendChild(b);
            return b;
        });

        function answered(fs) {
            if (fs.querySelector("input[type=radio]:checked")) { return true; }
            var text = fs.querySelector("input[type=text], textarea");
            if (text && text.value.trim()) { return true; }
            return Array.prototype.some.call(fs.querySelectorAll("select"), function (s) { return s.value; });
        }

        function paint() {
            dots.forEach(function (d, i) {
                d.classList.toggle("is-answered", answered(fieldsets[i]));
                if (i === current) { d.setAttribute("aria-current", "step"); } else { d.removeAttribute("aria-current"); }
            });
        }

        function show(i) {
            current = Math.max(0, Math.min(i, fieldsets.length - 1));
            fieldsets.forEach(function (fs, n) { fs.hidden = n !== current; });
            var last = current === fieldsets.length - 1;
            back.disabled = current === 0;
            next.hidden = last;
            if (actions) { actions.hidden = !last; }
            bar.style.width = ((current + 1) / fieldsets.length * 100) + "%";
            label.textContent = "Question " + (current + 1) + " of " + fieldsets.length;
            paint();
        }

        back.addEventListener("click", function () { show(current - 1); });
        next.addEventListener("click", function () { show(current + 1); });
        form.addEventListener("input", paint);
        form.addEventListener("change", paint);
        form.addEventListener("reset", function () { window.setTimeout(function () { show(0); }, 0); });
        form.classList.add("is-stepping");
        show(0);
    });
});
