document.addEventListener("DOMContentLoaded", function () {
    document.querySelectorAll(".mock-exam-timer").forEach(function (timer) {
        const form = timer.closest("form");
        const countdown = timer.querySelector(".mock-exam-countdown");
        const timeField = form.querySelector('input[name="time_taken_seconds"]');
        const duration = Number(timer.dataset.timeLimitMinutes) * 60;
        const startedAt = Date.now();

        if (!form || !countdown || !timeField || !Number.isFinite(duration) || duration <= 0) {
            return;
        }

        function updateTimer() {
            const elapsed = Math.floor((Date.now() - startedAt) / 1000);
            const remaining = Math.max(duration - elapsed, 0);
            const minutes = Math.floor(remaining / 60);
            const seconds = remaining % 60;
            timeField.value = String(Math.min(elapsed, duration));
            countdown.textContent = `${minutes}:${String(seconds).padStart(2, "0")}`;

            if (remaining === 0) {
                window.clearInterval(intervalId);
                form.requestSubmit();
            }
        }

        const intervalId = window.setInterval(updateTimer, 1000);
        form.addEventListener("submit", function () {
            timeField.value = String(Math.min(Math.floor((Date.now() - startedAt) / 1000), duration));
            window.clearInterval(intervalId);
        });
        updateTimer();
    });
});
