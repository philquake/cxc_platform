(function () {
	"use strict";
	/* The sample question: pick an answer, see the verdict and the explanation. */
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
