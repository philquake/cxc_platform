(function () {
    // Options are both hidden and disabled because Safari ignores `hidden` on <option>.
    function setOptionVisible(option, visible) {
        option.hidden = !visible;
        option.disabled = !visible && !option.selected;
    }

    function filterTopicsBySubject() {
        const subject = document.getElementById("id_subject");
        const topic = document.getElementById("id_topic");
        if (!subject || !topic) {
            return;
        }
        Array.from(topic.options).forEach(function (option) {
            if (!option.value) {
                return;
            }
            setOptionVisible(option, !subject.value || option.dataset.subject === subject.value);
        });
        const selected = topic.options[topic.selectedIndex];
        if (selected && selected.value && subject.value && selected.dataset.subject !== subject.value) {
            topic.value = "";
        }
    }

    function toggleMockFields() {
        const isMock = document.getElementById("id_is_mock");
        if (!isMock) {
            return;
        }
        // Mock exams span the whole subject; Quiz.clean() rejects a topic or lesson on them.
        ["topic", "lesson"].forEach(function (name) {
            const row = document.querySelector(".field-" + name);
            const input = document.getElementById("id_" + name);
            if (row) {
                row.hidden = isMock.checked;
            }
            if (input && isMock.checked) {
                input.value = "";
            }
        });
    }

    function questionSelects(group) {
        return group.querySelectorAll('select[name$="-question"]');
    }

    function applyDifficulty(group, difficulty) {
        questionSelects(group).forEach(function (select) {
            Array.from(select.options).forEach(function (option) {
                if (!option.value || !option.dataset.difficulty) {
                    return;
                }
                setOptionVisible(option, !difficulty || option.dataset.difficulty === difficulty);
            });
        });
    }

    function addDifficultyFilter() {
        const group = document.getElementById("quiz_questions-group");
        if (!group) {
            return;
        }
        const hasDifficulty = Array.from(questionSelects(group)).some(function (select) {
            return select.querySelector("option[data-difficulty]");
        });
        if (!hasDifficulty) {
            return;
        }
        const wrapper = document.createElement("div");
        wrapper.className = "quiz-question-filter";
        wrapper.innerHTML =
            '<label for="quiz-difficulty-filter">Show questions of difficulty</label>' +
            '<select id="quiz-difficulty-filter">' +
            '<option value="">All</option>' +
            '<option value="easy">Easy</option>' +
            '<option value="medium">Medium</option>' +
            '<option value="hard">Hard</option>' +
            "</select>";
        const heading = group.querySelector("h2");
        if (heading) {
            heading.insertAdjacentElement("afterend", wrapper);
        } else {
            group.prepend(wrapper);
        }
        const filter = wrapper.querySelector("select");
        filter.addEventListener("change", function () {
            applyDifficulty(group, filter.value);
        });
        document.addEventListener("formset:added", function () {
            applyDifficulty(group, filter.value);
        });
    }

    document.addEventListener("DOMContentLoaded", function () {
        const subject = document.getElementById("id_subject");
        const isMock = document.getElementById("id_is_mock");
        if (subject) {
            subject.addEventListener("change", filterTopicsBySubject);
            filterTopicsBySubject();
        }
        if (isMock) {
            isMock.addEventListener("change", toggleMockFields);
            toggleMockFields();
        }
        addDifficultyFilter();
    });
})();
