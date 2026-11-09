/* Spreadsheet formula practice: a small formula evaluator, no libraries. Output uses textContent only. */
(function () {
    "use strict";

    var COLS = "ABCDE";
    var DATA = {
        A1: "Item", B1: "Qty", C1: "Price", D1: "Total",
        A2: "Pens", B2: "10", C2: "2.5", A3: "Books", B3: "4", C3: "12", A4: "Bags", B4: "2", C4: "45",
        A5: "Rulers", B5: "15", C5: "1.2", A6: "Files", B6: "8", C6: "3.5", A7: "Markers", B7: "6", C7: "4",
        A9: "Total qty", A10: "Average price", A11: "Most expensive", A12: "Items with qty over 5", A13: "Qty of items over $3", A14: "Average total (1 dp)", A15: "Price of Bags"
    };
    for (var r = 2; r <= 7; r++) { DATA["D" + r] = "=B" + r + "*C" + r; }

    var CHALLENGES = [
        { cell: "B9", q: "In B9, find the total quantity of all items.", sol: "=SUM(B2:B7)" },
        { cell: "B10", q: "In B10, find the average price.", sol: "=AVERAGE(C2:C7)" },
        { cell: "B11", q: "In B11, find the highest price.", sol: "=MAX(C2:C7)" },
        { cell: "E2", q: "In E2, show \"Bulk\" if the quantity in B2 is 10 or more, otherwise \"Normal\".", sol: "=IF(B2>=10,\"Bulk\",\"Normal\")" },
        { cell: "B12", q: "In B12, count how many items have a quantity above 5.", sol: "=COUNTIF(B2:B7,\">5\")" },
        { cell: "B13", q: "In B13, add up the quantities of items whose price is above 3.", sol: "=SUMIF(C2:C7,\">3\",B2:B7)" },
        { cell: "B14", q: "In B14, find the average of the Total column, rounded to 1 decimal place.", sol: "=ROUND(AVERAGE(D2:D7),1)" },
        { cell: "B15", q: "In B15, look up the price of \"Bags\" from the table.", sol: "=VLOOKUP(\"Bags\",A2:D7,3,FALSE)" }
    ];

    /* ---------- evaluator ---------- */
    function colNum(s) { return COLS.indexOf(s) + 1; }
    function cellValue(cells, id, seen) {
        var raw = cells[id];
        if (raw === undefined || raw === "") { return ""; }
        if (raw.charAt(0) === "=") {
            if (seen[id]) { throw new Error("circular"); }
            seen[id] = true;
            var v = evaluate(raw, cells, seen);
            delete seen[id];
            return v;
        }
        return isFinite(raw) ? Number(raw) : raw;
    }
    function range(cells, a, b, seen) {
        var m1 = /^([A-Z])(\d+)$/.exec(a), m2 = /^([A-Z])(\d+)$/.exec(b), out = [];
        for (var c = Math.min(colNum(m1[1]), colNum(m2[1])); c <= Math.max(colNum(m1[1]), colNum(m2[1])); c++) {
            for (var r = Math.min(+m1[2], +m2[2]); r <= Math.max(+m1[2], +m2[2]); r++) { out.push(cellValue(cells, COLS.charAt(c - 1) + r, seen)); }
        }
        return out;
    }
    function flat(args) { return [].concat.apply([], args); }
    function nums(args) { return flat(args).filter(function (v) { return typeof v === "number"; }); }
    function matcher(crit) {
        var m = /^(<=|>=|<>|<|>|=)?(.*)$/.exec(String(crit)), op = m[1] || "=", t = m[2], n = t !== "" && isFinite(t) ? Number(t) : null;
        return function (v) {
            var a = n !== null && typeof v === "number" ? v : String(v).toLowerCase(), b = n !== null && typeof v === "number" ? n : t.toLowerCase();
            return op === "=" ? a === b : op === "<>" ? a !== b : op === "<" ? a < b : op === ">" ? a > b : op === "<=" ? a <= b : a >= b;
        };
    }
    var FN = {
        SUM: function (a) { return nums(a).reduce(function (x, y) { return x + y; }, 0); },
        AVERAGE: function (a) { var n = nums(a); if (!n.length) { throw new Error("#DIV/0!"); } return FN.SUM(a) / n.length; },
        MIN: function (a) { var n = nums(a); return n.length ? Math.min.apply(null, n) : 0; },
        MAX: function (a) { var n = nums(a); return n.length ? Math.max.apply(null, n) : 0; },
        COUNT: function (a) { return nums(a).length; },
        COUNTA: function (a) { return flat(a).filter(function (v) { return v !== ""; }).length; },
        COUNTIF: function (a) { var t = matcher(a[1]); return flat([a[0]]).filter(t).length; },
        SUMIF: function (a) {
            var t = matcher(a[1]), test = a[0], add = a[2] || a[0];
            return test.reduce(function (s, v, i) { return t(v) && typeof add[i] === "number" ? s + add[i] : s; }, 0);
        },
        IF: function (a) { return a[0] ? a[1] : (a.length > 2 ? a[2] : false); },
        AND: function (a) { return flat(a).every(Boolean); },
        OR: function (a) { return flat(a).some(Boolean); },
        ROUND: function (a) { var p = Math.pow(10, a[1] || 0); return Math.round((a[0] + Number.EPSILON) * p) / p; },
        ABS: function (a) { return Math.abs(a[0]); },
        VLOOKUP: function (a) {
            // The table arrives as a flat column-major list; width comes from the parsed range (a[4]).
            var key = a[0], w = a[4], h = a[1].length / w, col = a[2];
            for (var i = 0; i < h; i++) {
                if (String(a[1][i]).toLowerCase() === String(key).toLowerCase()) { return a[1][(col - 1) * h + i]; }
            }
            throw new Error("#N/A");
        }
    };

    function evaluate(formula, cells, seen) {
        var re = /\s*(?:("[^"]*")|(\d+\.?\d*|\.\d+)|(\$?[A-Z]\$?\d+)|([A-Z]+)(?=\()|(TRUE|FALSE)|(<>|<=|>=|[-+*\/^&=<>(),:%]))/gy;
        var toks = [], m, pos = 0, src = formula.slice(1);
        while (pos < src.length && (re.lastIndex = pos, m = re.exec(src))) { toks.push(m); pos = re.lastIndex; }
        if (src.slice(pos).trim()) { throw new Error("#NAME?"); }
        var i = 0;
        function peek() { return toks[i] && toks[i][6]; }
        function take(op) { if (peek() === op) { i++; return true; } return false; }
        function num(v) { if (typeof v === "boolean") { return +v; } if (v === "") { return 0; } if (typeof v !== "number") { throw new Error("#VALUE!"); } return v; }
        function compare() {
            var l = concat(), op;
            while (["=", "<>", "<", ">", "<=", ">="].indexOf(op = peek()) >= 0) {
                i++; var r = concat();
                if (typeof l === "string" || typeof r === "string") { l = String(l).toLowerCase(); r = String(r).toLowerCase(); }
                l = op === "=" ? l === r : op === "<>" ? l !== r : op === "<" ? l < r : op === ">" ? l > r : op === "<=" ? l <= r : l >= r;
            }
            return l;
        }
        function concat() { var l = add(); while (take("&")) { l = String(l) + String(add()); } return l; }
        function add() {
            var l = mul(), op;
            while ((op = peek()) === "+" || op === "-") { i++; var r = mul(); l = op === "+" ? num(l) + num(r) : num(l) - num(r); }
            return l;
        }
        function mul() {
            var l = pow(), op;
            while ((op = peek()) === "*" || op === "/") {
                i++; var r = num(pow());
                if (op === "/" && r === 0) { throw new Error("#DIV/0!"); }
                l = op === "*" ? num(l) * r : num(l) / r;
            }
            return l;
        }
        function pow() { var l = unary(); while (take("^")) { l = Math.pow(num(l), num(unary())); } return l; }
        function unary() { if (take("-")) { return -num(unary()); } if (take("+")) { return unary(); } return primary(); }
        function primary() {
            var t = toks[i++];
            if (!t) { throw new Error("#ERROR"); }
            if (t[1]) { return t[1].slice(1, -1); }
            if (t[2]) { return take("%") ? Number(t[2]) / 100 : Number(t[2]); }
            if (t[5]) { return t[5] === "TRUE"; }
            if (t[3]) {
                var a = t[3].replace(/\$/g, "");
                if (take(":")) {
                    var b = toks[i++]; if (!b || !b[3]) { throw new Error("#REF!"); }
                    return range(cells, a, b[3].replace(/\$/g, ""), seen || {});
                }
                return cellValue(cells, a, seen || {});
            }
            if (t[4]) {
                var name = t[4], args = [], w;
                i++; // "("
                if (!FN[name]) { throw new Error("#NAME?"); }
                if (!take(")")) {
                    do {
                        var start = i, v = compare();
                        if (name === "VLOOKUP" && args.length === 1 && Array.isArray(v)) { w = (function () { var s = toks[start][3].replace(/\$/g, ""), e = toks[i - 1][3].replace(/\$/g, ""); return Math.abs(colNum(e.charAt(0)) - colNum(s.charAt(0))) + 1; })(); }
                        args.push(v);
                    } while (take(","));
                    if (!take(")")) { throw new Error("#ERROR"); }
                }
                if (name === "VLOOKUP") { args[4] = w; }
                if (name === "IF" && args.length < 2) { throw new Error("#ERROR"); }
                return FN[name](args);
            }
            if (t[6] === "(") { var v2 = compare(); if (!take(")")) { throw new Error("#ERROR"); } return v2; }
            throw new Error("#ERROR");
        }
        var result = compare();
        if (i < toks.length) { throw new Error("#ERROR"); }
        if (Array.isArray(result)) { throw new Error("#VALUE!"); }
        return result;
    }

    function same(a, b) {
        return typeof a === "number" && typeof b === "number" ? Math.abs(a - b) < 1e-9 : String(a).toLowerCase() === String(b).toLowerCase() && typeof a === typeof b;
    }

    /* ---------- page ---------- */
    var index = 0, right = 0, tried = 0, mine = "";
    function $(id) { return document.getElementById(id); }
    function el(tag, text) { var n = document.createElement(tag); if (text !== undefined) { n.textContent = text; } return n; }
    function show(v) { return typeof v === "number" ? String(Math.round(v * 1e6) / 1e6) : typeof v === "boolean" ? String(v).toUpperCase() : String(v); }
    function say(cls, text) { var o = $("ss-result"); o.textContent = ""; var p = el("p", text); p.className = cls; o.appendChild(p); }

    function grid() {
        var cells = Object.assign({}, DATA), target = CHALLENGES[index].cell, t = $("ss-grid");
        if (mine) { cells[target] = mine; }
        t.textContent = "";
        var head = el("tr"); head.appendChild(el("th"));
        COLS.split("").forEach(function (c) { head.appendChild(el("th", c)); });
        t.appendChild(head);
        for (var r = 1; r <= 15; r++) {
            var tr = el("tr"); tr.appendChild(el("th", String(r)));
            COLS.split("").forEach(function (c) {
                var id = c + r, td = el("td", "");
                try { td.textContent = cells[id] === undefined ? "" : show(cellValue(cells, id, {})); } catch (e) { td.textContent = e.message; }
                if (id === target) { td.style.outline = "2px solid var(--color-accent)"; td.style.fontWeight = "700"; }
                tr.appendChild(td);
            });
            t.appendChild(tr);
        }
    }

    function load() {
        var c = CHALLENGES[index];
        mine = "";
        $("ss-prompt").textContent = (index + 1) + " of " + CHALLENGES.length + ". " + c.q;
        $("ss-target").textContent = c.cell;
        $("ss-in").value = "";
        $("ss-result").textContent = "";
        grid();
    }

    function check() {
        var f = $("ss-in").value.trim(), c = CHALLENGES[index];
        if (f.charAt(0) !== "=") { say("bin-error", "A formula starts with =."); return; }
        // Evaluate on the real data and on shifted numbers so a typed-in answer cannot pass.
        var ok = true, shifted = {};
        Object.keys(DATA).forEach(function (k) { shifted[k] = /^\d+\.?\d*$/.test(DATA[k]) ? String(Number(DATA[k]) + 3) : DATA[k]; });
        try {
            [DATA, shifted].forEach(function (d) {
                var a = Object.assign({}, d), b = Object.assign({}, d);
                a[c.cell] = f; b[c.cell] = c.sol;
                ok = ok && same(cellValue(a, c.cell, {}), cellValue(b, c.cell, {}));
            });
        } catch (e) { say("bin-error", "Your formula gives " + e.message); return; }
        tried++; right += ok ? 1 : 0;
        say(ok ? "bin-ok" : "bin-error", ok ? "Correct." : "Not quite: it gives the wrong value, either now or when the data changes.");
        $("ss-score").textContent = right + " of " + tried + " checks correct";
    }

    document.addEventListener("DOMContentLoaded", function () {
        $("ss-in").addEventListener("input", function () { mine = $("ss-in").value.trim().charAt(0) === "=" ? $("ss-in").value.trim() : ""; grid(); });
        $("ss-in").addEventListener("keydown", function (e) { if (e.key === "Enter") { check(); } });
        $("ss-check").addEventListener("click", check);
        $("ss-hint").addEventListener("click", function () { $("ss-in").value = CHALLENGES[index].sol; mine = CHALLENGES[index].sol; grid(); });
        $("ss-next").addEventListener("click", function () { index = (index + 1) % CHALLENGES.length; load(); });
        load();
    });
})();
