(function () {
	"use strict";
	/* Content below the first screen rises in as it scrolls into view, on every page. */
	Array.prototype.forEach.call(document.querySelectorAll(".quiz-card, .progress-block, .progress-subject, .legal-section, a.content-card, .lesson-content h2, .lesson-content h3, .lesson-content img, .lesson-content table, .lesson-content blockquote, .unit"), function (el) {
		if (!el.hasAttribute("data-reveal") && el.getBoundingClientRect().top > window.innerHeight) { el.setAttribute("data-reveal", ""); }
	});
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
