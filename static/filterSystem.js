/**
 * filterSystem.js — Shared Excel-style column filter engine
 *
 * Usage:
 *   initFilterSystem({
 *     tableSelector: '#studentsTable',
 *     data:          LOCAL_DATA,       // raw JSON array from server
 *     keys:          DATA_KEYS,        // ordered column key array
 *     tableConfig:   { ... }           // DataTable overrides (language, etc.)
 *   });
 *
 * All optimizations:
 *   1. Pre-normalise data (all values → trimmed strings) once at load
 *   2. Compile ACTIVE_FILTERS to Set objects for O(1) lookup
 *   3. Single-pass filter with compiled predicates
 *   4. Redraw without pagination reset (table.draw(false))
 *   5. Short-circuit when no filters are active
 *   6. Cache unique column values (single scan of data)
 *   7. Lazy-populate filter panels (first open only)
 *   8. Extracted to reusable module (this file)
 */

/* exported initFilterSystem */
function initFilterSystem(opts) {
    'use strict';

    var tableSelector = opts.tableSelector;
    var DATA_KEYS = opts.keys;
    var tableConfig = opts.tableConfig || {};
    var headerRowSelector = opts.headerRowSelector || '#headerRow';
    var filterRowSelector = opts.filterRowSelector || '#filterRow';

    /* ──────────────────────────────────────────────────────────
       1. Pre-normalise LOCAL_DATA — all values become strings
       ────────────────────────────────────────────────────────── */
    var LOCAL_DATA = opts.data.map(function (row) {
        var out = {};
        for (var k in row) {
            if (Object.prototype.hasOwnProperty.call(row, k)) {
                var v = row[k];
                out[k] = (v === null || v === undefined) ? '' : String(v).trim();
            }
        }
        return out;
    });

    /* ──────────────────────────────────────────────────────────
       6. Cache unique values per column (single scan)
       ────────────────────────────────────────────────────────── */
    var COLUMN_UNIQUE_VALUES = {};
    DATA_KEYS.forEach(function (k) { COLUMN_UNIQUE_VALUES[k] = new Set(); });
    LOCAL_DATA.forEach(function (row) {
        DATA_KEYS.forEach(function (k) { COLUMN_UNIQUE_VALUES[k].add(row[k]); });
    });

    /* ── Global filter state ────────────────────────────────── */
    var ACTIVE_FILTERS = {};

    /* ── 7. Lazy-populate tracking ──────────────────────────── */
    var FILTER_POPULATED = {};
    /* ── Pre-filter function (set by external caller) ───── */
    var preFilterFn = null;
    /* ── Build filter cells (buttons in table, panels on body) ── */
    var $fr = $(filterRowSelector);
    var cols = $(headerRowSelector + ' th').length;
    for (var i = 0; i < cols; i++) {
        $fr.append(
            '<th><div class="cf-wrap">' +
            '<button type="button" class="cf-btn" data-col="' + i + '">\u25BC All</button>' +
            '</div></th>'
        );
        $('body').append(
            '<div class="cf-panel" data-col="' + i + '">' +
            '  <input type="text" class="cf-search" placeholder="Search values\u2026">' +
            '  <div class="cf-batch">' +
            '    <button type="button" class="cf-sel">Select All</button>' +
            '    <button type="button" class="cf-desel">Deselect All</button>' +
            '  </div>' +
            '  <ul class="cf-list"></ul>' +
            '  <div class="cf-foot">' +
            '    <span class="cf-count"></span>' +
            '    <button type="button" class="cf-apply">Apply</button>' +
            '  </div>' +
            '</div>'
        );
    }

    /* ── DataTable init ─────────────────────────────────────── */
    var dtDefaults = {
        data: LOCAL_DATA,
        columns: DATA_KEYS.map(function (k) { return { data: k }; }),
        order: [[0, 'asc']],
        pageLength: 25,
        lengthMenu: [10, 25, 50, 100, 500],
        scrollX: true,
        deferRender: true,
        searching: true,
        dom: '<"dt-top-bar"lf>rt<"dt-bottom-bar"ip>'
    };

    // Merge caller overrides (e.g. language)
    for (var key in tableConfig) {
        if (Object.prototype.hasOwnProperty.call(tableConfig, key)) {
            dtDefaults[key] = tableConfig[key];
        }
    }

    var table = $(tableSelector).DataTable(dtDefaults);

    /* ──────────────────────────────────────────────────────────
       2 + 3 + 4 + 5.  Optimised filter engine
       ────────────────────────────────────────────────────────── */
    function applyAllFilters() {
        var baseData = preFilterFn ? LOCAL_DATA.filter(preFilterFn) : LOCAL_DATA;
        var keys = Object.keys(ACTIVE_FILTERS);

        /* 5. Short-circuit: no column filters → show pre-filtered set */
        if (keys.length === 0) {
            table.rows().remove();
            table.rows.add(baseData);
            table.draw(false);
            return;
        }

        /* 2. Compile to Set objects for O(1) lookup */
        var compiled = [];
        for (var i = 0; i < keys.length; i++) {
            var vals = ACTIVE_FILTERS[keys[i]];
            if (vals && vals.length > 0) {
                compiled.push({ key: keys[i], set: new Set(vals) });
            }
        }

        if (compiled.length === 0) {
            table.rows().remove();
            table.rows.add(baseData);
            table.draw(false);
            return;
        }

        /* 3. Single-pass filter with compiled predicates */
        var filtered = baseData.filter(function (row) {
            for (var j = 0; j < compiled.length; j++) {
                if (!compiled[j].set.has(row[compiled[j].key])) return false;
            }
            return true;
        });

        /* 4. Redraw without pagination reset */
        table.rows().remove();
        table.rows.add(filtered);
        table.draw(false);
    }

    /* ──────────────────────────────────────────────────────────
       Populate a single column filter from cached unique values
       ────────────────────────────────────────────────────────── */
    function populateColumnFilter(colIndex) {
        var key = DATA_KEYS[colIndex];
        var $list = getPanel(colIndex).find('.cf-list');
        $list.empty();

        /* Read from cached set — no re-scan needed */
        var seen = {};
        COLUMN_UNIQUE_VALUES[key].forEach(function (raw) {
            var norm = raw.toLowerCase();
            if (!(norm in seen)) seen[norm] = raw;
        });

        var vals = Object.keys(seen).map(function (k) { return seen[k]; });
        vals.sort(function (a, b) {
            if (a === '') return -1;
            if (b === '') return 1;
            return a.localeCompare(b, undefined, { numeric: true });
        });

        var html = '';
        vals.forEach(function (val) {
            var label = val === '' ? '(Blank)' : val;
            var safeVal = $('<i>').text(val).html();
            var safeLbl = $('<span>').text(label).html();
            html += '<li data-val="' + safeVal + '">' +
                '<label><input type="checkbox" checked>' +
                '<span>' + safeLbl + '</span></label></li>';
        });
        $list.html(html);
        countUpdate(colIndex);
    }

    /* ── Helpers ─────────────────────────────────────────────── */
    function getPanel(col) {
        return $('body > .cf-panel[data-col="' + col + '"]');
    }

    function countUpdate(col) {
        var $p = getPanel(col);
        var tot = $p.find('.cf-list li').length;
        var chk = $p.find('.cf-list li input:checked').length;
        $p.find('.cf-count').text(chk + ' / ' + tot);
    }

    function applyFilter(col) {
        var key = DATA_KEYS[col];
        var $p = getPanel(col);
        var $lis = $p.find('.cf-list li');
        var tot = $lis.length;
        var sel = [];
        $lis.each(function () {
            if ($(this).find('input').is(':checked')) sel.push($(this).attr('data-val'));
        });

        var $btn = $('.cf-btn[data-col="' + col + '"]');
        if (sel.length === 0 || sel.length === tot) {
            delete ACTIVE_FILTERS[key];
            $btn.text('\u25BC All').removeClass('cf-active');
        } else {
            ACTIVE_FILTERS[key] = sel;
            $btn.text('\u25BC ' + sel.length + ' sel').addClass('cf-active');
        }
        applyAllFilters();
    }

    /* ── Event handlers (document-level) ─────────────────────── */

    // Open / close panel  +  7. Lazy populate on first open
    $(document).on('click', '.cf-btn', function (e) {
        e.stopPropagation();
        var col = $(this).data('col');
        var colKey = DATA_KEYS[col];
        var $panel = getPanel(col);
        var open = $panel.hasClass('open');

        $('.cf-panel.open').removeClass('open');

        if (!open) {
            /* 7. Lazy populate — build checkbox list on first open only */
            if (!FILTER_POPULATED[colKey]) {
                populateColumnFilter(col);
                FILTER_POPULATED[colKey] = true;
            }

            var r = this.getBoundingClientRect();
            $panel.css({ top: r.bottom + 2, left: r.left }).addClass('open');
            var pw = $panel.outerWidth();
            if (r.left + pw > window.innerWidth) $panel.css('left', window.innerWidth - pw - 8);
            $panel.find('.cf-search').val('').trigger('input').focus();
        }
    });

    // Search inside panel
    $(document).on('input', '.cf-search', function () {
        var term = this.value.toLowerCase();
        $(this).closest('.cf-panel').find('.cf-list li').each(function () {
            $(this).toggle($(this).find('span').text().toLowerCase().indexOf(term) !== -1);
        });
    });

    // Checkbox toggle
    $(document).on('click', '.cf-list li', function (e) {
        if (!$(e.target).is('input[type="checkbox"]')) {
            var cb = $(this).find('input[type="checkbox"]')[0];
            cb.checked = !cb.checked;
        }
        countUpdate($(this).closest('.cf-panel').data('col'));
    });

    // Prevent label double-toggle
    $(document).on('click', '.cf-list li label', function (e) {
        e.preventDefault();
    });

    // Select All visible
    $(document).on('click', '.cf-sel', function () {
        var $p = $(this).closest('.cf-panel');
        $p.find('.cf-list li:visible input').prop('checked', true);
        countUpdate($p.data('col'));
    });

    // Deselect All visible
    $(document).on('click', '.cf-desel', function () {
        var $p = $(this).closest('.cf-panel');
        $p.find('.cf-list li:visible input').prop('checked', false);
        countUpdate($p.data('col'));
    });

    // Apply — filter + close
    $(document).on('click', '.cf-apply', function () {
        var col = $(this).closest('.cf-panel').data('col');
        applyFilter(col);
        getPanel(col).removeClass('open');
    });

    // Close panels on outside click
    $(document).on('mousedown', function (e) {
        if (!$(e.target).closest('.cf-panel, .cf-btn').length)
            $('.cf-panel.open').removeClass('open');
    });

    /* ── Public API ──────────────────────────────────────── */
    return {
        setPreFilter: function (fn) {
            preFilterFn = fn || null;
            applyAllFilters();
        },
        getColumnFilters: function () {
            return JSON.parse(JSON.stringify(ACTIVE_FILTERS));
        },
        setColumnFilters: function (filters) {
            ACTIVE_FILTERS = filters || {};
            for (var i = 0; i < DATA_KEYS.length; i++) {
                var k = DATA_KEYS[i];
                var $btn = $('.cf-btn[data-col="' + i + '"]:first');
                if (ACTIVE_FILTERS[k] && ACTIVE_FILTERS[k].length > 0) {
                    $btn.text('\u25BC ' + ACTIVE_FILTERS[k].length + ' sel').addClass('cf-active');
                    if (FILTER_POPULATED[k]) {
                        var $panel = getPanel(i);
                        var allowed = new Set(ACTIVE_FILTERS[k]);
                        $panel.find('.cf-list li').each(function () {
                            $(this).find('input').prop('checked', allowed.has($(this).attr('data-val')));
                        });
                        countUpdate(i);
                    }
                } else {
                    $btn.text('\u25BC All').removeClass('cf-active');
                    if (FILTER_POPULATED[k]) {
                        getPanel(i).find('.cf-list li input').prop('checked', true);
                        countUpdate(i);
                    }
                }
            }
            applyAllFilters();
        },
        clearColumnFilters: function () {
            ACTIVE_FILTERS = {};
            $('.cf-btn').text('\u25BC All').removeClass('cf-active');
            Object.keys(FILTER_POPULATED).forEach(function (k) {
                var idx = DATA_KEYS.indexOf(k);
                if (idx >= 0) {
                    getPanel(idx).find('.cf-list li input').prop('checked', true);
                    countUpdate(idx);
                }
            });
            applyAllFilters();
        },
        getCurrentData: function () {
            var baseData = preFilterFn ? LOCAL_DATA.filter(preFilterFn) : LOCAL_DATA;
            var keys = Object.keys(ACTIVE_FILTERS);
            if (keys.length === 0) return baseData.slice();
            var compiled = [];
            for (var i = 0; i < keys.length; i++) {
                var vals = ACTIVE_FILTERS[keys[i]];
                if (vals && vals.length > 0) compiled.push({ key: keys[i], set: new Set(vals) });
            }
            if (compiled.length === 0) return baseData.slice();
            return baseData.filter(function (row) {
                for (var j = 0; j < compiled.length; j++) {
                    if (!compiled[j].set.has(row[compiled[j].key])) return false;
                }
                return true;
            });
        },
        getRawData: function () { return LOCAL_DATA; },
        getTable: function () { return table; }
    };
}
