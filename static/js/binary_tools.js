/* Binary converter: number bases, signed numbers, binary arithmetic, ASCII, BCD and floating point.
   Everything runs in the browser. Results are built with textContent only, never innerHTML. */
(function () {
    "use strict";

    var DIGITS = "0123456789abcdefghijklmnopqrstuvwxyz";
    var MAX_FRAC = 24;

    function $(id) { return document.getElementById(id); }

    function el(tag, cls, text) {
        var node = document.createElement(tag);
        if (cls) { node.className = cls; }
        if (text !== undefined) { node.textContent = text; }
        return node;
    }

    function clear(node) { while (node.firstChild) { node.removeChild(node.firstChild); } }

    function fail(out, message) {
        clear(out);
        out.appendChild(el("p", "bin-error", message));
    }

    function card(title, value, note) {
        var c = el("div", "bin-card");
        c.appendChild(el("span", "bin-card-title", title));
        c.appendChild(el("code", "bin-card-value", value));
        if (note) { c.appendChild(el("span", "bin-card-note", note)); }
        return c;
    }

    function lines(out, list) {
        list.forEach(function (text) { out.appendChild(el("p", "bin-line", text)); });
    }

    function table(head, rows) {
        var t = el("table", "bin-table");
        var tr = el("tr");
        head.forEach(function (h) { tr.appendChild(el("th", "", h)); });
        t.appendChild(el("thead")).appendChild(tr);
        var body = el("tbody");
        rows.forEach(function (r) {
            var row = el("tr");
            r.forEach(function (cell) { row.appendChild(el("td", "", cell)); });
            body.appendChild(row);
        });
        t.appendChild(body);
        var wrap = el("div", "bin-table-wrap");
        wrap.appendChild(t);
        return wrap;
    }

    function group4(bits) {
        return bits.replace(/(?=(?:[01]{4})+$)/g, " ").trim();
    }

    function intValue(id, lo, hi, fallback) {
        var n = parseInt($(id).value, 10);
        if (isNaN(n)) { return fallback; }
        return Math.min(hi, Math.max(lo, n));
    }

    function pickBase(selectId, customId) {
        var v = $(selectId).value;
        return v === "custom" ? intValue(customId, 2, 36, 2) : parseInt(v, 10);
    }

    function label(base) {
        return { 2: "Binary", 8: "Octal", 10: "Decimal", 16: "Hex" }[base] || "Base " + base;
    }

    /* ---------- exact rational helpers (BigInt) ---------- */

    function parseNumber(text, base) {
        var s = text.trim().toLowerCase().replace(/[\s_]/g, "");
        var neg = false;
        if (s[0] === "-" || s[0] === "+") { neg = s[0] === "-"; s = s.slice(1); }
        if (!s || s === ".") { throw new Error("Enter a number."); }
        var parts = s.split(".");
        if (parts.length > 2) { throw new Error("A number can have only one point."); }
        var b = BigInt(base);
        var whole = 0n, fnum = 0n, fden = 1n;
        function digit(ch) {
            var d = DIGITS.indexOf(ch);
            if (d < 0 || d >= base) { throw new Error("“" + ch + "” is not a base-" + base + " digit."); }
            return BigInt(d);
        }
        Array.from(parts[0]).forEach(function (ch) { whole = whole * b + digit(ch); });
        Array.from(parts[1] || "").forEach(function (ch) { fnum = fnum * b + digit(ch); fden *= b; });
        return { neg: neg, whole: whole, fnum: fnum, fden: fden, intDigits: parts[0], fracDigits: parts[1] || "" };
    }

    // num/den written in decimal, e.g. 5n/8n -> "0.625"
    function ratToDecimal(num, den, max) {
        var out = (num / den).toString();
        var rem = num % den;
        if (rem === 0n) { return out; }
        out += ".";
        for (var i = 0; i < max && rem !== 0n; i++) {
            rem *= 10n;
            out += (rem / den).toString();
            rem %= den;
        }
        return out + (rem !== 0n ? "…" : "");
    }

    function convert(p, base) {
        var b = BigInt(base);
        var n = p.whole, digits = "", steps = [];
        if (n === 0n) { digits = "0"; }
        while (n > 0n) {
            var q = n / b, r = n % b;
            steps.push([n.toString(), q.toString(), DIGITS[Number(r)]]);
            digits = DIGITS[Number(r)] + digits;
            n = q;
        }
        var frac = "", fsteps = [], num = p.fnum, exact = true;
        for (var i = 0; num > 0n; i++) {
            if (i === MAX_FRAC) { exact = false; break; }
            var prod = num * b, d = prod / p.fden;
            fsteps.push([ratToDecimal(num, p.fden, 12), ratToDecimal(prod, p.fden, 12), DIGITS[Number(d)]]);
            frac += DIGITS[Number(d)];
            num = prod % p.fden;
        }
        return { digits: digits, steps: steps, frac: frac, fsteps: fsteps, exact: exact };
    }

    function written(p, c) {
        var s = (p.neg && (p.whole !== 0n || p.fnum !== 0n) ? "-" : "") + c.digits;
        if (c.frac) { s += "." + c.frac + (c.exact ? "" : "…"); }
        return s.toUpperCase();
    }

    /* ---------- tab: number bases ---------- */

    function renderBase() {
        var out = $("base-out"), steps = $("base-steps");
        $("base-from-custom-wrap").hidden = $("base-from").value !== "custom";
        $("base-to-custom-wrap").hidden = $("base-work").value !== "custom";
        clear(steps);
        var from = pickBase("base-from", "base-from-custom");
        var work = pickBase("base-work", "base-to-custom");
        var p;
        try { p = parseNumber($("base-in").value, from); } catch (e) { return fail(out, e.message); }

        clear(out);
        [2, 8, 10, 16].forEach(function (base) {
            out.appendChild(card(label(base), written(p, convert(p, base)), "base " + base));
        });

        buildBaseSteps(steps, p, from, work);
    }

    function buildBaseSteps(steps, p, from, work) {
        var target = convert(p, work);
        steps.appendChild(el("h3", "", "Working: base " + from + " to base " + work));
        if (from === work) {
            steps.appendChild(el("p", "bin-line", "The number is already in base " + work + "."));
            return;
        }

        if (from !== 10) {
            var terms = [];
            Array.from(p.intDigits.toLowerCase()).forEach(function (ch, i, arr) {
                terms.push(parseInt(ch, 36) + " × " + from + "^" + (arr.length - 1 - i));
            });
            Array.from(p.fracDigits.toLowerCase()).forEach(function (ch, i) {
                terms.push(parseInt(ch, 36) + " × " + from + "^-" + (i + 1));
            });
            if (terms.length <= 40) {
                lines(steps, ["Place values: " + terms.join(" + ")]);
            }
            var dec = written(p, convert(p, 10));
            lines(steps, ["Value in decimal = " + dec]);
        }

        var shortcut = groupingHint(p, from, work);
        if (shortcut) { lines(steps, [shortcut]); }
        if (work === 10) { return; }

        if (from !== 10) { lines(steps, ["Now convert the decimal value to base " + work + "."]); }
        steps.appendChild(el("h4", "", "Whole part: divide by " + work + ", read the remainders from the bottom up"));
        steps.appendChild(table(["Number", "÷ " + work + " (quotient)", "Remainder"],
            target.steps.length ? target.steps : [["0", "0", "0"]]));
        if (target.fsteps.length) {
            steps.appendChild(el("h4", "", "Fraction: multiply by " + work + ", read the whole numbers from the top down"));
            steps.appendChild(table(["Fraction", "× " + work, "Digit"], target.fsteps));
            if (!target.exact) { lines(steps, ["The fraction does not end, so it is cut off after " + MAX_FRAC + " places."]); }
        }
        lines(steps, ["Answer: " + written(p, target)]);
    }

    // Binary <-> octal/hex is done by grouping bits (3 for octal, 4 for hex).
    function groupingHint(p, from, to) {
        var size = { 8: 3, 16: 4 };
        var bin = from === 2 ? to : (to === 2 ? from : 0);
        if (!size[bin]) { return ""; }
        var k = size[bin];
        if (from === 2) {
            var ip = p.intDigits, fp = p.fracDigits;
            while (ip.length % k) { ip = "0" + ip; }
            while (fp.length % k) { fp += "0"; }
            var chop = function (s) { return s.match(new RegExp(".{" + k + "}", "g")) || []; };
            var conv = function (g) { return parseInt(g, 2).toString(bin).toUpperCase(); };
            var gi = chop(ip), gf = chop(fp);
            return "Shortcut: group the bits in " + k + "s from the point (" + gi.join(" ") + (gf.length ? " . " + gf.join(" ") : "") +
                ") and convert each group: " + gi.map(conv).join("") + (gf.length ? "." + gf.map(conv).join("") : "");
        }
        var each = function (s) {
            return Array.from(s.toLowerCase()).map(function (ch) { return parseInt(ch, 36).toString(2).padStart(k, "0"); });
        };
        var a = each(p.intDigits), f = each(p.fracDigits);
        return "Shortcut: write each digit as " + k + " bits: " + a.join(" ") + (f.length ? " . " + f.join(" ") : "");
    }

    /* ---------- tab: signed numbers ---------- */

    function mask(bits) { return (1n << BigInt(bits)) - 1n; }

    function encodeSigned(n, bits) {
        var half = 1n << BigInt(bits - 1);
        var m = mask(bits);
        var abs = n < 0n ? -n : n;
        var rangeSm = "−" + (half - 1n) + " to +" + (half - 1n);
        var okSm = abs <= half - 1n;
        return [
            { name: "Sign and magnitude", range: rangeSm, pat: okSm ? ((n < 0n ? half : 0n) | abs) : null },
            { name: "One's complement", range: rangeSm, pat: okSm ? (n < 0n ? m ^ abs : abs) : null },
            { name: "Two's complement", range: "−" + half + " to +" + (half - 1n), pat: n >= -half && n < half ? BigInt.asUintN(bits, n) : null }
        ];
    }

    function decodeSigned(pat, bits) {
        var half = 1n << BigInt(bits - 1);
        var m = mask(bits);
        var neg = pat >= half;
        var low = pat & (half - 1n);
        return [
            neg ? (low === 0n ? "−0" : "−" + low) : low.toString(),
            neg ? (pat === m ? "−0" : "−" + (m ^ pat)) : pat.toString(),
            (neg ? pat - (1n << BigInt(bits)) : pat).toString().replace("-", "−")
        ];
    }

    function renderSigned() {
        var out = $("signed-out");
        var binary = $("signed-mode").value === "bin";
        $("signed-bits-wrap").hidden = binary;
        var text = $("signed-in").value.trim().replace(/\s/g, "");
        var names = ["Sign and magnitude", "One's complement", "Two's complement"];
        try {
            if (binary) {
                if (!/^[01]+$/.test(text)) { throw new Error("Type a pattern of 0s and 1s."); }
                if (text.length < 2 || text.length > 64) { throw new Error("Use between 2 and 64 bits."); }
                var bits = text.length, pat = BigInt("0b" + text), vals = decodeSigned(pat, bits);
                clear(out);
                out.appendChild(table(["Representation", "Value of " + group4(text)], names.map(function (n, i) { return [n, vals[i]]; })));
                lines(out, ["Unsigned, the same pattern is " + pat + "."]);
                return;
            }
            if (!/^[+-]?\d+$/.test(text)) { throw new Error("Type a whole number, such as -45."); }
            var nbits = intValue("signed-bits", 2, 64, 8);
            var n = BigInt(text);
            var reps = encodeSigned(n, nbits);
            clear(out);
            out.appendChild(table(["Representation", nbits + "-bit pattern", "Range"], reps.map(function (r) {
                return [r.name, r.pat === null ? "does not fit" : group4(r.pat.toString(2).padStart(nbits, "0")), r.range];
            })));
            if (n < 0n && reps[2].pat !== null) {
                var abs = (-n).toString(2).padStart(nbits, "0");
                var inv = abs.replace(/[01]/g, function (c) { return c === "0" ? "1" : "0"; });
                lines(out, [
                    "Two's complement of " + n + ": write " + (-n) + " in " + nbits + " bits = " + group4(abs) +
                    ", invert every bit = " + group4(inv) + ", add 1 = " + group4(reps[2].pat.toString(2).padStart(nbits, "0")) + "."
                ]);
            }
        } catch (e) { fail(out, e.message); }
    }

    /* ---------- tab: binary arithmetic ---------- */

    function toSigned(pat, bits) { return pat >= (1n << BigInt(bits - 1)) ? pat - (1n << BigInt(bits)) : pat; }

    function arithCompute(a, b, bits, minus) {
        var m = mask(bits);
        var addend = minus ? ((m ^ b) + 1n) & m : b;
        var carries = [], carry = 0n, sum = 0n;
        for (var i = 0; i < bits; i++) {
            var t = ((a >> BigInt(i)) & 1n) + ((addend >> BigInt(i)) & 1n) + carry;
            carries.push(carry);
            sum |= (t & 1n) << BigInt(i);
            carry = t >> 1n;
        }
        var trueValue = minus ? toSigned(a, bits) - toSigned(b, bits) : toSigned(a, bits) + toSigned(b, bits);
        var lo = -(1n << BigInt(bits - 1)), hi = (1n << BigInt(bits - 1)) - 1n;
        return {
            m: m, addend: addend, sum: sum, carry: carry, intoSign: carries[bits - 1],
            cin: carries.slice().reverse().join(""), trueValue: trueValue, lo: lo, hi: hi,
            overflow: trueValue < lo || trueValue > hi
        };
    }

    function arithRows(a, b, bits, minus, c) {
        var pad = function (v) { return v.toString(2).padStart(bits, "0"); };
        var w = bits + 3;
        var row = function (name, s) { return (name + ":").padEnd(w, " ") + s.split("").join(" "); };
        var rows = [row("carries", c.cin), row("A", pad(a)), row("B", pad(b))];
        if (minus) { rows.push(row("invert B", pad(c.m ^ b)), row("+1 = -B", pad(c.addend))); }
        rows.push("".padEnd(w + bits * 2 - 1, "─"), row("result", pad(c.sum)));
        return rows.join("\n");
    }

    function arithNotes(out, a, b, bits, c) {
        lines(out, [
            "A = " + toSigned(a, bits) + ", B = " + toSigned(b, bits) + " (as two's complement).",
            "Result " + group4(c.sum.toString(2).padStart(bits, "0")) + " = " + toSigned(c.sum, bits) + (c.overflow ? "" : " (correct: " + c.trueValue + ")."),
            "Carry out of the top bit: " + c.carry + ". Carry into the sign bit: " + c.intoSign + "."
        ]);
        out.appendChild(el("p", c.overflow ? "bin-error" : "bin-ok", c.overflow
            ? "Overflow: the true answer " + c.trueValue + " does not fit in " + bits + " bits (range " + c.lo + " to " + c.hi + ")."
            : "No overflow."));
    }

    function renderArith() {
        var out = $("arith-out");
        var bits = intValue("arith-bits", 2, 64, 8);
        var minus = $("arith-op").value === "-";
        var sa = $("arith-a").value.replace(/\s/g, ""), sb = $("arith-b").value.replace(/\s/g, "");
        if (!/^[01]+$/.test(sa) || !/^[01]+$/.test(sb)) { return fail(out, "Type A and B as binary numbers (0s and 1s)."); }
        if (sa.length > bits || sb.length > bits) { return fail(out, "A and B must fit in " + bits + " bits."); }

        var a = BigInt("0b" + sa), b = BigInt("0b" + sb);
        var c = arithCompute(a, b, bits, minus);
        clear(out);
        out.appendChild(el("pre", "bin-pre", arithRows(a, b, bits, minus, c)));
        arithNotes(out, a, b, bits, c);
    }

    /* ---------- tab: text and ASCII ---------- */

    function renderText() {
        var out = $("text-out");
        var mode = $("text-mode").value, fmt = parseInt($("text-fmt").value, 10);
        var input = $("text-in").value;
        if (!input) { return fail(out, "Type something to convert."); }
        var fmtCode = function (cp) {
            return fmt === 2 ? cp.toString(2).padStart(8, "0") : (fmt === 16 ? cp.toString(16).toUpperCase().padStart(2, "0") : String(cp));
        };
        clear(out);
        if (mode === "enc") {
            var chars = Array.from(input), rows = [];
            chars.forEach(function (ch) {
                var cp = ch.codePointAt(0);
                rows.push([cp < 33 || cp === 127 ? (cp === 32 ? "space" : "ctrl") : ch, String(cp), cp.toString(2).padStart(8, "0"), cp.toString(16).toUpperCase().padStart(2, "0")]);
            });
            out.appendChild(card("Codes", chars.map(function (ch) { return fmtCode(ch.codePointAt(0)); }).join(" ")));
            if (chars.length <= 200) { out.appendChild(table(["Character", "Decimal", "Binary", "Hex"], rows)); }
            return;
        }
        var tokens = input.trim().split(/[\s,]+/).filter(Boolean);
        if (fmt === 2 && tokens.length === 1 && tokens[0].length > 8 && tokens[0].length % 8 === 0) {
            tokens = tokens[0].match(/.{8}/g);
        }
        var text = "";
        for (var i = 0; i < tokens.length; i++) {
            var t = fmt === 16 ? tokens[i].replace(/^0x/i, "") : tokens[i];
            var ok = fmt === 2 ? /^[01]+$/.test(t) : (fmt === 16 ? /^[0-9a-f]+$/i.test(t) : /^\d+$/.test(t));
            var cp = ok ? parseInt(t, fmt) : NaN;
            if (isNaN(cp) || cp > 0x10ffff || (cp >= 0xd800 && cp <= 0xdfff)) {
                return fail(out, "“" + tokens[i] + "” is not a valid " + label(fmt).toLowerCase() + " character code.");
            }
            text += String.fromCodePoint(cp);
        }
        out.appendChild(card("Text", text));
    }

    /* ---------- tab: BCD ---------- */

    function renderBcd() {
        var out = $("bcd-out");
        var text = $("bcd-in").value.replace(/\s/g, "");
        if (!text) { return fail(out, "Enter a value."); }
        clear(out);
        if ($("bcd-mode").value === "enc") {
            if (!/^\d+$/.test(text)) { return fail(out, "Type a whole number using digits 0 to 9."); }
            var groups = text.split("").map(function (d) { return parseInt(d, 10).toString(2).padStart(4, "0"); });
            out.appendChild(card("BCD", groups.join(" ")));
            out.appendChild(table(["Digit", "8421 code"], text.split("").map(function (d, i) { return [d, groups[i]]; })));
            var pure = BigInt(text).toString(2);
            lines(out, ["Pure binary: " + group4(pure.padStart(Math.ceil(pure.length / 4) * 4, "0")) + " (" + pure.length + " bits, against " + groups.length * 4 + " bits in BCD)."]);
            return;
        }
        if (!/^[01]+$/.test(text)) { return fail(out, "Type 0s and 1s only."); }
        if (text.length % 4) { return fail(out, "BCD uses groups of 4 bits; this has " + text.length + " bits."); }
        var digits = "", rows = [];
        for (var i = 0; i < text.length; i += 4) {
            var g = text.slice(i, i + 4), v = parseInt(g, 2);
            if (v > 9) { return fail(out, g + " is " + v + ", which is not a decimal digit. BCD groups must be 0000 to 1001."); }
            digits += v;
            rows.push([g, String(v)]);
        }
        out.appendChild(card("Decimal", digits.replace(/^0+(?=\d)/, "")));
        out.appendChild(table(["Group", "Digit"], rows));
    }

    /* ---------- tab: floating point ---------- */

    function bitsOf(n, width) { return BigInt.asUintN(width, BigInt(n)).toString(2).padStart(width, "0"); }

    function floatVisibility() {
        var cape = $("float-fmt").value === "cape", enc = $("float-mode").value === "enc";
        $("float-dec-wrap").hidden = !enc;
        $("float-mb-wrap").hidden = !(cape && enc);
        $("float-eb-wrap").hidden = !(cape && enc);
        $("float-m-wrap").hidden = !(cape && !enc);
        $("float-e-wrap").hidden = !(cape && !enc);
        $("float-hex-wrap").hidden = cape || enc;
    }

    function capeEncode(x, mb, eb, out) {
        var emin = -Math.pow(2, eb - 1), emax = Math.pow(2, eb - 1) - 1;
        var scale = Math.pow(2, mb - 1), M, e;
        if (x === 0) {
            M = 0; e = emin;
        } else {
            e = Math.floor(Math.log2(Math.abs(x))) + 1;
            var m = x / Math.pow(2, e);
            while (m >= 1 || m < -1) { m /= 2; e++; }
            while (Math.abs(m) < 0.5) { m *= 2; e--; }
            if (m === -0.5) { m = -1; e--; }
            M = Math.round(m * scale);
            if (M === scale) { M = scale / 2; e++; }
            if (M === -scale / 2) { M = -scale; e--; }
        }
        if (e > emax) { return fail(out, "Too large: it needs exponent " + e + ", but " + eb + " bits only reach " + emax + "."); }
        if (e < emin) { return fail(out, "Too small: it needs exponent " + e + ", but " + eb + " bits only reach " + emin + "."); }

        var mant = bitsOf(M, mb), exp = bitsOf(e, eb);
        var stored = (M / scale) * Math.pow(2, e);
        clear(out);
        out.appendChild(card("Mantissa", mant[0] + "." + mant.slice(1), mb + " bits"));
        out.appendChild(card("Exponent", exp, eb + " bits, two's complement"));
        out.appendChild(card("Stored value", String(stored), stored === x ? "exact" : "rounded from " + x));
        if (x !== 0) {
            lines(out, [
                "Find the exponent that puts the mantissa between 0.5 and 1 (or −1 and −0.5): " + x + " ÷ 2^" + e + " = " + (x / Math.pow(2, e)) + ".",
                "Write the mantissa as a " + mb + "-bit two's complement fraction: " + mant[0] + "." + mant.slice(1) + ".",
                "Write the exponent " + e + " in " + eb + " bits: " + exp + "."
            ]);
        }
    }

    function capeDecode(ms, es, out) {
        ms = ms.replace(/[\s.]/g, ""); es = es.replace(/\s/g, "");
        if (!/^[01]{2,52}$/.test(ms) || !/^[01]{2,11}$/.test(es)) { return fail(out, "Type the mantissa (2–52 bits) and exponent (2–11 bits) as 0s and 1s."); }
        var M = Number(toSigned(BigInt("0b" + ms), ms.length)), e = Number(toSigned(BigInt("0b" + es), es.length));
        var m = M / Math.pow(2, ms.length - 1), value = m * Math.pow(2, e);
        clear(out);
        out.appendChild(card("Value", String(value)));
        lines(out, [
            "Mantissa " + ms[0] + "." + ms.slice(1) + " = " + m + ". Exponent " + es + " = " + e + ".",
            "Value = " + m + " × 2^" + e + " = " + value + ".",
            ms[0] !== ms[1] || M === 0 ? (M === 0 ? "" : "This is not normalised: the first two mantissa bits should differ.") : "Normalised: the first two mantissa bits differ."
        ].filter(Boolean));
    }

    function ieeeParts(bits, width) {
        var eb = width === 32 ? 8 : 11, bias = width === 32 ? 127 : 1023;
        var sign = bits[0], exp = bits.slice(1, 1 + eb), frac = bits.slice(1 + eb);
        var e = parseInt(exp, 2);
        var kind = e === 0 ? (/^0+$/.test(frac) ? "zero" : "subnormal") : (e === (1 << eb) - 1 ? (/^0+$/.test(frac) ? "infinity" : "NaN") : "normal");
        return { sign: sign, exp: exp, frac: frac, e: e, bias: bias, kind: kind };
    }

    function ieeeShow(bits, width, out, x) {
        var p = ieeeParts(bits, width);
        clear(out);
        out.appendChild(card("Sign | exponent | fraction", p.sign + " | " + p.exp + " | " + p.frac));
        out.appendChild(card("Hex", BigInt("0b" + bits).toString(16).toUpperCase().padStart(width / 4, "0")));
        out.appendChild(card("Value", String(x), p.kind));
        if (p.kind === "normal") {
            lines(out, ["Sign " + p.sign + " = " + (p.sign === "1" ? "negative" : "positive") + ". Exponent " + p.exp + " = " + p.e + ", minus the bias " + p.bias + " = " + (p.e - p.bias) + ".",
                "Value = (" + (p.sign === "1" ? "−1" : "+1") + ") × 1." + p.frac.replace(/0+$/, "") + " (binary) × 2^" + (p.e - p.bias) + "."]);
        } else if (p.kind === "subnormal") {
            lines(out, ["Exponent field is all 0s with a non-zero fraction: a subnormal number, 0." + p.frac.replace(/0+$/, "") + " (binary) × 2^" + (1 - p.bias) + "."]);
        }
    }

    function renderFloat() {
        floatVisibility();
        var out = $("float-out");
        var fmt = $("float-fmt").value, enc = $("float-mode").value === "enc";
        if (fmt === "cape") {
            if (!enc) { return capeDecode($("float-m").value, $("float-e").value, out); }
            var s = $("float-in").value.trim();
            var x = s === "" ? NaN : Number(s);
            if (!isFinite(x)) { return fail(out, "Type a decimal number, such as -6.75."); }
            return capeEncode(x, intValue("float-mb", 3, 52, 8), intValue("float-eb", 2, 11, 4), out);
        }
        var width = fmt === "ieee32" ? 32 : 64;
        var view = new DataView(new ArrayBuffer(8));
        if (enc) {
            var t = $("float-in").value.trim().toLowerCase();
            var v = t === "inf" || t === "infinity" ? Infinity : (t === "-inf" ? -Infinity : (t === "nan" ? NaN : (t === "" ? NaN : Number(t))));
            if (isNaN(v) && t !== "nan") { return fail(out, "Type a decimal number, such as -6.75."); }
            var bits;
            if (width === 32) { view.setFloat32(0, v); bits = view.getUint32(0).toString(2).padStart(32, "0"); }
            else { view.setFloat64(0, v); bits = view.getBigUint64(0).toString(2).padStart(64, "0"); }
            var stored = width === 32 ? view.getFloat32(0) : view.getFloat64(0);
            ieeeShow(bits, width, out, stored);
            if (isFinite(v) && stored !== v) { lines(out, ["Not stored exactly: " + v + " is rounded to the nearest representable value."]); }
            return;
        }
        var raw = $("float-hex").value.replace(/\s/g, "");
        var b;
        if (/^[01]+$/.test(raw) && raw.length === width) { b = raw; }
        else {
            var h = raw.replace(/^0x/i, "");
            if (!/^[0-9a-f]+$/i.test(h) || h.length !== width / 4) { return fail(out, "Type " + width + " bits or " + width / 4 + " hex digits."); }
            b = BigInt("0x" + h).toString(2).padStart(width, "0");
        }
        var val;
        if (width === 32) { view.setUint32(0, parseInt(b, 2)); val = view.getFloat32(0); }
        else { view.setBigUint64(0, BigInt("0b" + b)); val = view.getFloat64(0); }
        ieeeShow(b, width, out, val);
    }

    /* ---------- tab: practice ---------- */

    var practice = { current: null, checked: false, wired: false, right: 0, tried: 0, streak: 0 };

    function rnd(n) { return Math.floor(Math.random() * n); }
    function pick(list) { return list[rnd(list.length)]; }

    function norm(text, base) {
        var s = text.trim().toLowerCase().replace(/[\s_]/g, "");
        var prefix = { 2: "0b", 16: "0x", 8: "0o" }[base];
        return prefix && s.indexOf(prefix) === 0 ? s.slice(2) : s;
    }

    // Exact comparison, so leading zeros, case and 0b/0x prefixes do not matter.
    function sameNumber(input, expected, base) {
        try {
            var a = parseNumber(norm(input, base), base);
            return a.neg === expected.neg && a.whole === expected.whole && a.fnum * expected.fden === expected.fnum * a.fden;
        } catch (e) { return false; }
    }

    function makeBase(level) {
        var bases = [2, 8, 10, 16];
        var from = pick(bases), to = pick(bases.filter(function (b) { return b !== from; }));
        var frac = "";
        if (level && ((from === 2 && to === 10) || (from === 10 && to === 2)) && rnd(2)) {
            frac = "." + Array.from({ length: 1 + rnd(3) }, function () { return rnd(2); }).join("");
        }
        var pb = parseNumber((rnd(level ? 1000 : 64) + 1).toString(2) + frac, 2);
        var text = written(pb, convert(pb, from));
        var src = parseNumber(text, from);
        var answer = written(src, convert(src, to));
        var expected = parseNumber(answer, to);
        return {
            prompt: "Convert " + text + " from " + label(from).toLowerCase() + " to " + label(to).toLowerCase() + ".",
            answer: answer,
            check: function (i) { return sameNumber(i, expected, to); },
            working: function (c) { buildBaseSteps(c, src, from, to); }
        };
    }

    function makeTwos(level) {
        var bits = level ? 8 : 4, half = 1 << (bits - 1);
        if (rnd(2)) {
            var n = rnd(2) ? -(rnd(half) + 1) : rnd(half - 1) + 1;
            var raw = BigInt.asUintN(bits, BigInt(n)).toString(2).padStart(bits, "0");
            return {
                prompt: "Write " + String(n).replace("-", "−") + " as a " + bits + "-bit two's complement number.",
                answer: group4(raw),
                check: function (i) { return norm(i, 2) === raw; },
                working: function (c) {
                    if (n >= 0) { return lines(c, ["Positive numbers are written as ordinary binary, padded to " + bits + " bits: " + group4(raw) + "."]); }
                    var abs = (-n).toString(2).padStart(bits, "0");
                    var inv = abs.replace(/[01]/g, function (ch) { return ch === "0" ? "1" : "0"; });
                    lines(c, ["Write " + (-n) + " in " + bits + " bits: " + group4(abs) + ".", "Invert every bit: " + group4(inv) + ".", "Add 1: " + group4(raw) + "."]);
                }
            };
        }
        var pat = rnd((1 << bits) - 1) + 1, text = pat.toString(2).padStart(bits, "0");
        var value = decodeSigned(BigInt(pat), bits)[2];
        return {
            prompt: "What decimal number is the " + bits + "-bit two's complement pattern " + group4(text) + "?",
            answer: value,
            check: function (i) { return i.trim().replace(/[−–]/g, "-").replace(/^\+/, "") === value.replace("−", "-"); },
            working: function (c) {
                var terms = [];
                text.split("").forEach(function (bit, idx) {
                    if (bit === "1") { terms.push(idx === 0 ? "−" + half : String(1 << (bits - 1 - idx))); }
                });
                lines(c, ["The leftmost bit is worth −" + half + "; the others are worth 1, 2, 4… as usual.",
                    "Add the place values of the 1 bits: " + terms.join(" + ") + " = " + value + "."]);
            }
        };
    }

    function makeArith(level) {
        var bits = level ? 8 : 4, minus = rnd(2) === 1;
        var a = BigInt(rnd(1 << bits)), b = BigInt(rnd(1 << bits));
        var c = arithCompute(a, b, bits, minus);
        var pa = a.toString(2).padStart(bits, "0"), pb = b.toString(2).padStart(bits, "0");
        var expr = pa + (minus ? " − " : " + ") + pb;
        var sum = c.sum.toString(2).padStart(bits, "0");
        var working = function (out) {
            out.appendChild(el("pre", "bin-pre", arithRows(a, b, bits, minus, c)));
            arithNotes(out, a, b, bits, c);
        };
        if (level && rnd(2)) {
            return {
                prompt: "Using " + bits + "-bit two's complement, does " + expr + " overflow? (yes or no)",
                answer: c.overflow ? "yes" : "no",
                check: function (i) { var t = i.trim().toLowerCase(); return (t === "yes" || t === "y" || t === "no" || t === "n") && (t[0] === "y") === c.overflow; },
                working: working
            };
        }
        return {
            prompt: "Work out " + expr + " in " + bits + "-bit two's complement. Give the " + bits + "-bit result.",
            answer: sum,
            check: function (i) { return norm(i, 2) === sum; },
            working: working
        };
    }

    function makeAscii(level) {
        var cp = level ? 33 + rnd(94) : 65 + rnd(26), ch = String.fromCharCode(cp);
        var base = pick([2, 10, 16]);
        var code = base === 2 ? cp.toString(2).padStart(8, "0") : cp.toString(base).toUpperCase();
        var working = function (c) {
            lines(c, ["“" + ch + "” has ASCII code " + cp + " in decimal, " + cp.toString(2).padStart(8, "0") + " in binary and " + cp.toString(16).toUpperCase() + " in hex.",
                "Anchors to remember: A = 65, a = 97, 0 = 48. Letters run in order from there."]);
        };
        if (rnd(3) === 0) {
            return {
                prompt: "Which character has the ASCII code " + code + " (" + label(base).toLowerCase() + ")?",
                answer: ch,
                check: function (i) { return i.trim() === ch; },
                working: working
            };
        }
        var expected = parseNumber(cp.toString(base), base);
        return {
            prompt: "What is the ASCII code of “" + ch + "” in " + label(base).toLowerCase() + "?",
            answer: code,
            check: function (i) { return sameNumber(i, expected, base); },
            working: working
        };
    }

    function makeBcd(level) {
        var digits = String(level ? 100 + rnd(9900) : 10 + rnd(90));
        var groups = digits.split("").map(function (d) { return parseInt(d, 10).toString(2).padStart(4, "0"); });
        var working = function (c) {
            c.appendChild(table(["Digit", "8421 code"], digits.split("").map(function (d, i) { return [d, groups[i]]; })));
        };
        if (rnd(2)) {
            return {
                prompt: "Write " + digits + " in BCD.",
                answer: groups.join(" "),
                check: function (i) { return i.replace(/\s/g, "") === groups.join(""); },
                working: working
            };
        }
        return {
            prompt: "Convert the BCD number " + groups.join(" ") + " to decimal.",
            answer: digits,
            check: function (i) { return i.replace(/\s/g, "") === digits; },
            working: working
        };
    }

    function makeFloat(level) {
        var x = (1 + rnd(level ? 120 : 20)) / pick(level ? [1, 2, 4, 8] : [1, 2, 4]);
        if (rnd(2)) { x = -x; }
        var enc = el("div", "bin-out");
        capeEncode(x, 8, 4, enc);
        var vals = enc.querySelectorAll(".bin-card-value");
        var mant = vals[0].textContent, exp = vals[1].textContent;
        if (rnd(2)) {
            return {
                prompt: "Write " + x + " as a normalised floating-point number with an 8-bit mantissa and a 4-bit exponent, both in two's complement. Give the mantissa, a space, then the exponent.",
                answer: mant + " " + exp,
                check: function (i) {
                    var t = i.trim().replace(/\./g, "").split(/[\s,]+/);
                    return t.length === 2 && t[0] === mant.replace(".", "") && t[1] === exp;
                },
                working: function (c) { c.appendChild(enc.cloneNode(true)); }
            };
        }
        var dec = el("div", "bin-out");
        capeDecode(mant, exp, dec);
        return {
            prompt: "A number is stored with mantissa " + mant + " and exponent " + exp + " (both two's complement). What is its decimal value?",
            answer: String(x),
            check: function (i) { return i.trim() !== "" && Number(i.trim().replace(/−/g, "-")) === x; },
            working: function (c) { c.appendChild(dec.cloneNode(true)); }
        };
    }

    var GENERATORS = { base: makeBase, twos: makeTwos, arith: makeArith, ascii: makeAscii, bcd: makeBcd, float: makeFloat };

    function practiceScore() {
        $("prac-score").textContent = practice.tried
            ? practice.right + " of " + practice.tried + " correct" + (practice.streak > 1 ? ", " + practice.streak + " in a row" : "")
            : "No answers yet.";
    }

    function practiceNext(focus) {
        var level = $("prac-level").value === "exam" ? 1 : 0;
        var kinds = Object.keys(GENERATORS).filter(function (k) { return $("prac-" + k).checked; });
        clear($("prac-result")); clear($("prac-working"));
        $("prac-in").value = "";
        practice.checked = false;
        if (!kinds.length) {
            practice.current = null;
            $("prac-prompt").textContent = "Tick at least one question type.";
            return;
        }
        practice.current = GENERATORS[pick(kinds)](level);
        $("prac-prompt").textContent = practice.current.prompt;
        if (focus) { $("prac-in").focus(); }
    }

    function practiceWorking() {
        var box = $("prac-working");
        clear(box);
        if (!practice.current) { return; }
        box.appendChild(el("h3", "", "Working"));
        practice.current.working(box);
    }

    function practiceCheck() {
        var cur = practice.current, result = $("prac-result");
        if (!cur || practice.checked) { return; }
        clear(result);
        if (!$("prac-in").value.trim()) { return result.appendChild(el("p", "bin-error", "Type an answer first.")); }
        var ok = cur.check($("prac-in").value);
        practice.checked = true;
        practice.tried++;
        practice.right += ok ? 1 : 0;
        practice.streak = ok ? practice.streak + 1 : 0;
        result.appendChild(el("p", ok ? "bin-ok" : "bin-error", ok ? "Correct." : "Not quite. The answer is " + cur.answer + "."));
        if (!ok) { practiceWorking(); }
        practiceScore();
    }

    // Called on every input in the panel (see wiring below); only the first call does anything.
    function renderPractice() {
        if (practice.wired) { return; }
        practice.wired = true;
        $("prac-check").addEventListener("click", practiceCheck);
        $("prac-work").addEventListener("click", practiceWorking);
        $("prac-next").addEventListener("click", function () { practiceNext(true); });
        $("prac-in").addEventListener("keydown", function (event) {
            if (event.key !== "Enter") { return; }
            event.preventDefault();
            if (practice.checked) { practiceNext(true); } else { practiceCheck(); }
        });
        $("prac-options").addEventListener("change", function () { practiceNext(true); });
        practiceScore();
        practiceNext(false);
    }

    /* ---------- tabs and wiring ---------- */

    var PANELS = { base: renderBase, signed: renderSigned, arith: renderArith, text: renderText, bcd: renderBcd, float: renderFloat, practice: renderPractice };

    function selectTab(name, focus) {
        Object.keys(PANELS).forEach(function (key) {
            var tab = $("tab-" + key), on = key === name;
            tab.setAttribute("aria-selected", on ? "true" : "false");
            tab.tabIndex = on ? 0 : -1;
            $("panel-" + key).hidden = !on;
            if (on && focus) { tab.focus(); }
        });
        try { history.replaceState(null, "", "#" + name); } catch (e) { /* hash is optional */ }
    }

    document.addEventListener("DOMContentLoaded", function () {
        var names = Object.keys(PANELS);
        names.forEach(function (name, i) {
            $("tab-" + name).addEventListener("click", function () { selectTab(name); });
            $("tab-" + name).addEventListener("keydown", function (event) {
                var step = event.key === "ArrowRight" ? 1 : (event.key === "ArrowLeft" ? -1 : 0);
                if (!step) { return; }
                event.preventDefault();
                selectTab(names[(i + step + names.length) % names.length], true);
            });
            $("panel-" + name).addEventListener("input", PANELS[name]);
            $("panel-" + name).addEventListener("change", PANELS[name]);
            PANELS[name]();
        });
        // ?x=5 pre-fills the number (optional ?base=2|8|10|16 says what base it is in), so a link can open on an answer.
        var q = new URLSearchParams(location.search), x = q.get("x");
        if (x) {
            $("base-in").value = x.slice(0, 200);
            if (["2", "8", "10", "16"].indexOf(q.get("base")) >= 0) { $("base-from").value = q.get("base"); }
            else { $("base-from").value = "10"; }
            renderBase();
        }
        var wanted = location.hash.slice(1);
        if (PANELS[wanted]) { selectTab(wanted); }
    });
})();
