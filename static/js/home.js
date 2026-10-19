(function () {
	"use strict";
	var reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
	var clamp = function (n, lo, hi) { return Math.min(hi, Math.max(lo, n)); };

	/* ---- the sample question ---- */
	var card = document.querySelector(".q");
	if (card) {
		var code = card.querySelector(".q-console code");
		var right = card.querySelector("[data-correct]").getAttribute("data-value");
		Array.prototype.forEach.call(card.querySelectorAll(".q-option"), function (button) {
			button.addEventListener("click", function () {
				var ok = button.hasAttribute("data-correct");
				card.classList.add("is-answered");
				card.classList.toggle("is-right", ok);
				card.classList.toggle("is-wrong", !ok);
				code.textContent = ok
					? "build passed: " + right + " is correct"
					: "error: " + button.getAttribute("data-value") + " is not the answer. Expected " + right + ".";
				card.querySelector(".q-next").focus();
			});
		});
		card.querySelector(".q-next").addEventListener("click", function () {
			card.classList.remove("is-answered", "is-right", "is-wrong");
			card.querySelector(".q-option").focus();
		});
	}

	/* ---- the return: one picture at three distances ---- */
	var ret = document.getElementById("return");
	function returnScroll() {
		var rect = ret.getBoundingClientRect();
		var span = ret.offsetHeight - ret.firstElementChild.offsetHeight;
		if (span <= 0) { return; }
		var p = clamp(-rect.top / span, 0, 0.999);
		var stage = Math.floor(p * 3) + 1;
		ret.className = ret.className.replace(/\bs[123]\b/g, "").trim() + " s" + stage;
	}

	/* ---- the rest: the picture settles as it passes ---- */
	var rest = document.querySelector(".rest");
	function restScroll() {
		var rect = rest.getBoundingClientRect();
		var p = clamp(1 - (rect.top + rect.height) / (window.innerHeight + rect.height), 0, 1);
		rest.style.setProperty("--rest-scale", (1.1 - 0.1 * p).toFixed(3));
	}

	var ticking = false;
	function onScroll() {
		if (ticking) { return; }
		ticking = true;
		requestAnimationFrame(function () {
			ticking = false;
			if (ret) { returnScroll(); }
			if (rest && !reduce) { restScroll(); }
		});
	}
	window.addEventListener("scroll", onScroll, { passive: true });
	window.addEventListener("resize", onScroll);
	onScroll();

	/* ---- entrances ---- */
	var targets = document.querySelectorAll("[data-reveal]");
	if (!("IntersectionObserver" in window) || reduce) {
		Array.prototype.forEach.call(targets, function (el) { el.classList.add("is-in"); });
		return;
	}
	var io = new IntersectionObserver(function (entries) {
		entries.forEach(function (entry) {
			if (entry.isIntersecting) { entry.target.classList.add("is-in"); io.unobserve(entry.target); }
		});
	}, { threshold: 0.2 });
	Array.prototype.forEach.call(targets, function (el) { io.observe(el); });
})();
