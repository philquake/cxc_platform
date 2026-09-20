(function () {
    function insertSelectedImage() {
        const select = document.getElementById("lesson-image-select");
        const editors = window.editors || {};
        const editor = editors.id_content || editors.content || Object.values(editors)[0];
        const option = select && select.options[select.selectedIndex];

        if (!select || !option || !option.value) {
            return;
        }

        if (!editor) {
            window.alert("The lesson editor is still loading. Please try again.");
            return;
        }

        editor.execute("insertImage", {
            source: option.value,
            altText: option.dataset.alt || "",
        });
        editor.editing.view.focus();
        select.value = "";
    }

    document.addEventListener("DOMContentLoaded", function () {
        const button = document.getElementById("lesson-image-insert");
        if (button) {
            button.addEventListener("click", insertSelectedImage);
        }
    });
})();