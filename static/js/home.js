(function () {
	"use strict";
	/* The sample question: pick an answer, see the verdict and the explanation. */
	/* Headline words rise in one after another (the text itself is unchanged). */
	var title = document.querySelector(".hero h1");
	if (title && document.documentElement.classList.contains("js")) {
		title.innerHTML = title.textContent.trim().split(/\s+/).map(function (word, i) {
			return '<span class="w" style="--i:' + i + '">' + word.replace(/&/g, "&amp;").replace(/</g, "&lt;") + "</span>";
		}).join(" ");
	}

	/* Exam countdown: days left and the lessons a week that finishes the biggest course (3 a day at most, as in the study plan). */
	var countdown = document.querySelector(".countdown");
	if (countdown) {
		countdown.hidden = false;
		var input = countdown.querySelector("input");
		var out = countdown.querySelector(".countdown-out");
		var lessons = parseInt(countdown.getAttribute("data-lessons"), 10);
		input.min = new Date(Date.now() + 864e5).toISOString().slice(0, 10);
		input.addEventListener("input", function () {
			var days = Math.ceil((new Date(input.value + "T00:00:00") - new Date().setHours(0, 0, 0, 0)) / 864e5);
			if (!input.value || !(days > 0)) { out.textContent = ""; return; }
			var perDay = lessons / days;
			out.textContent = days + " day" + (days === 1 ? "" : "s") + " to go. " + (perDay > 3
				? "That is tight: at 3 lessons a day you would cover " + days * 3 + " of the " + lessons + " lessons in the biggest course."
				: "About " + Math.max(1, Math.ceil(perDay * 7)) + " lessons a week finishes the biggest course (" + lessons + " lessons).");
		});
	}

	var card = document.querySelector(".q");
	if (!card) { return; }
	var options = Array.prototype.slice.call(card.querySelectorAll(".q-option"));
	var verdict = card.querySelector(".q-verdict");
	var right = card.querySelector("[data-correct]").getAttribute("data-value");

	options.forEach(function (button) {
		button.addEventListener("click", function () {
			var ok = button.hasAttribute("data-correct");
			card.classList.add("is-answered");
			card.classList.toggle("is-right", ok);
			card.classList.toggle("is-wrong", !ok);
			options.forEach(function (o) {
				o.disabled = true;
				if (o.hasAttribute("data-correct")) { o.classList.add("is-correct"); }
			});
			if (!ok) { button.classList.add("is-wrong"); }
			verdict.textContent = ok ? "Correct. It is a " + right + "." : "Not quite. The answer is " + right + ".";
			card.querySelector(".q-next").focus();
		});
	});

	card.querySelector(".q-next").addEventListener("click", function () {
		card.classList.remove("is-answered", "is-right", "is-wrong");
		options.forEach(function (o) { o.disabled = false; o.classList.remove("is-correct", "is-wrong"); });
		options[0].focus();
	});
})();
