(function () {
	"use strict";
	var targets = document.querySelectorAll("[data-reveal]");
	var reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
	if (!("IntersectionObserver" in window) || reduce) {
		Array.prototype.forEach.call(targets, function (el) { el.classList.add("is-in"); });
		return;
	}
	var io = new IntersectionObserver(function (entries) {
		entries.forEach(function (entry) {
			if (entry.isIntersecting) { entry.target.classList.add("is-in"); io.unobserve(entry.target); }
		});
	}, { threshold: 0.15 });
	Array.prototype.forEach.call(targets, function (el) { io.observe(el); });
})();
