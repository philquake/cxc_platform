/* SQL practice: sql.js (SQLite in WebAssembly) runs in the browser. Output is built with textContent only. */
(function () {
    "use strict";

    var SEED = "CREATE TABLE students(student_id INTEGER PRIMARY KEY, first_name TEXT, last_name TEXT, form INTEGER, parish TEXT, age INTEGER);" +
        "CREATE TABLE results(result_id INTEGER PRIMARY KEY, student_id INTEGER, subject TEXT, score INTEGER, term INTEGER);" +
        "INSERT INTO students VALUES (1,'Ava','Brown',5,'Kingston',16),(2,'Jamal','Clarke',5,'St Andrew',17),(3,'Kemar','Reid',4,'St Catherine',15)," +
        "(4,'Shanice','Gordon',5,'Manchester',16),(5,'Dwayne','Lewis',4,'Kingston',15),(6,'Tia','Campbell',6,'Clarendon',18)," +
        "(7,'Omar','Walker',6,'St Andrew',17),(8,'Nia','Thomas',4,'St James',16);" +
        "INSERT INTO results VALUES (1,1,'IT',88,1),(2,1,'Maths',74,1),(3,2,'IT',65,1),(4,2,'Maths',58,1),(5,3,'IT',91,1),(6,3,'Maths',80,1)," +
        "(7,4,'IT',72,1),(8,4,'Maths',69,1),(9,5,'IT',55,1),(10,5,'Maths',49,1),(11,6,'IT',95,1),(12,6,'Maths',85,1)," +
        "(13,7,'IT',78,1),(14,7,'Maths',90,1),(15,8,'IT',61,1),(16,1,'IT',92,2),(17,2,'IT',70,2),(18,3,'IT',89,2);";

    // Marked by running both queries: same rows (and same order when the solution sorts) is a pass.
    var CHALLENGES = [
        { q: "List the first and last names of every student in form 5.", sql: "SELECT first_name, last_name FROM students WHERE form = 5;" },
        { q: "Show all students from Kingston, sorted by last name.", sql: "SELECT * FROM students WHERE parish = 'Kingston' ORDER BY last_name;" },
        { q: "How many students are there in total?", sql: "SELECT COUNT(*) FROM students;" },
        { q: "Find the average age of the students.", sql: "SELECT AVG(age) FROM students;" },
        { q: "Show the subject and score of every result with a score of 80 or more, highest first.", sql: "SELECT subject, score FROM results WHERE score >= 80 ORDER BY score DESC;" },
        { q: "For each subject, show the subject and its highest score.", sql: "SELECT subject, MAX(score) FROM results GROUP BY subject;" },
        { q: "Show each student's first name with the score of every IT result they have.", sql: "SELECT first_name, score FROM students JOIN results ON students.student_id = results.student_id WHERE subject = 'IT';" },
        { q: "List the first names of students whose average score is above 75.", sql: "SELECT first_name FROM students JOIN results ON students.student_id = results.student_id GROUP BY students.student_id HAVING AVG(score) > 75;" },
        { q: "Show the first names of students who have no Maths result in term 2.", sql: "SELECT first_name FROM students WHERE student_id NOT IN (SELECT student_id FROM results WHERE subject = 'Maths' AND term = 2);" }
    ];

    var SQL, db, index = 0, right = 0, tried = 0, solved = false;

    function $(id) { return document.getElementById(id); }
    function el(tag, cls, text) { var n = document.createElement(tag); if (cls) { n.className = cls; } if (text !== undefined) { n.textContent = text; } return n; }
    function say(cls, text) { var out = $("sql-result"); out.textContent = ""; out.appendChild(el("p", cls, text)); }

    function reset() { if (db) { db.close(); } db = new SQL.Database(); db.run(SEED); }

    function table(result) {
        var wrap = el("div", "bin-table-wrap"), t = el("table", "bin-table"), head = el("tr");
        result.columns.forEach(function (c) { head.appendChild(el("th", "", c)); });
        t.appendChild(el("thead")).appendChild(head);
        var body = el("tbody");
        result.values.forEach(function (row) {
            var tr = el("tr");
            row.forEach(function (v) { tr.appendChild(el("td", "", v === null ? "NULL" : String(v))); });
            body.appendChild(tr);
        });
        t.appendChild(body);
        wrap.appendChild(t);
        return wrap;
    }

    function run() {
        var out = $("sql-result");
        try {
            var results = db.exec($("sql-in").value);
            out.textContent = "";
            if (!results.length) { say("bin-ok", "Done. The statement ran and returned no rows."); return; }
            results.forEach(function (r) { out.appendChild(table(r)); });
        } catch (e) { say("bin-error", e.message); }
    }

    function rows(query) {
        var r = db.exec(query);
        return r.length ? r[0].values.map(function (v) { return JSON.stringify(v); }) : [];
    }

    function check() {
        var c = CHALLENGES[index], ordered = /order by/i.test(c.sql);
        if (solved) { return; }
        // Marking runs on a clean copy so earlier INSERT/UPDATE/DELETE experiments cannot change the expected answer.
        var mine, want, saved = db;
        try {
            db = new SQL.Database(); db.run(SEED);
            want = rows(c.sql);
            mine = rows($("sql-in").value);
        } catch (e) { db.close(); db = saved; say("bin-error", e.message); return; }
        db.close(); db = saved;
        if (!ordered) { mine.sort(); want.sort(); }
        var ok = JSON.stringify(mine) === JSON.stringify(want);
        tried++; right += ok ? 1 : 0; solved = ok;
        say(ok ? "bin-ok" : "bin-error", ok ? "Correct. Your query returns the expected rows." : "Not quite. Your query returned " + mine.length + " row(s); " + want.length + " expected. Run it and compare, or ask for a solution.");
        $("sql-score").textContent = right + " of " + tried + " checks correct";
    }

    function show() {
        var c = CHALLENGES[index];
        $("sql-prompt").textContent = (index + 1) + " of " + CHALLENGES.length + ". " + c.q;
        $("sql-in").value = "";
        $("sql-result").textContent = "";
        solved = false;
    }

    document.addEventListener("DOMContentLoaded", function () {
        if (typeof initSqlJs !== "function") { $("sql-prompt").textContent = "The SQL engine could not load. Check your connection and refresh."; return; }
        initSqlJs({ locateFile: function (f) { return "https://cdnjs.cloudflare.com/ajax/libs/sql.js/1.8.0/" + f; } }).then(function (lib) {
            SQL = lib; reset(); show();
            $("sql-in").value = "SELECT * FROM students;";
            $("sql-run").addEventListener("click", run);
            $("sql-check").addEventListener("click", check);
            $("sql-hint").addEventListener("click", function () { $("sql-in").value = CHALLENGES[index].sql; });
            $("sql-next").addEventListener("click", function () { index = (index + 1) % CHALLENGES.length; show(); });
            $("sql-reset").addEventListener("click", function () { reset(); say("bin-ok", "Database reset."); });
            $("sql-in").addEventListener("keydown", function (e) { if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) { run(); } });
        }, function () { $("sql-prompt").textContent = "The SQL engine could not load. Check your connection and refresh."; });
    });
})();
