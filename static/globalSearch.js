/**
 * Global Student Search — autocomplete search in the navbar
 * Requires jQuery. Include this script after jQuery on any page with the global search bar.
 */
(function () {
    var debounceTimer = null;
    var $input = $('#globalSearch');
    var $results = $('#globalSearchResults');

    if (!$input.length) return;

    $input.on('input', function () {
        var q = $(this).val().trim();
        clearTimeout(debounceTimer);
        if (q.length < 2) {
            $results.hide().empty();
            return;
        }
        debounceTimer = setTimeout(function () {
            $.getJSON('/api/search?q=' + encodeURIComponent(q), function (res) {
                if (!res.results || res.results.length === 0) {
                    $results.html('<div class="gs-empty">No students found</div>').show();
                    return;
                }
                var html = '';
                res.results.forEach(function (s) {
                    var badge = '';
                    if (s.status === 'Placed') badge = '<span class="badge bg-success ms-2" style="font-size:0.65rem;">Placed</span>';
                    var course = s.course || '';
                    if (course.length > 40) course = course.substring(0, 40) + '…';
                    html += '<a class="gs-item" href="/student/' + encodeURIComponent(s.reg_no) + '">';
                    html += '<div class="gs-name">' + (s.student_name || '') + badge + '</div>';
                    html += '<div class="gs-meta">' + s.reg_no + ' · ' + course + '</div>';
                    html += '</a>';
                });
                $results.html(html).show();
            });
        }, 250);
    });

    // Hide results on outside click
    $(document).on('click', function (e) {
        if (!$(e.target).closest('.global-search-wrap').length) {
            $results.hide();
        }
    });

    // Re-show on focus if has content
    $input.on('focus', function () {
        if ($results.children().length && $(this).val().trim().length >= 2) {
            $results.show();
        }
    });

    // Navigate to student on Enter (first result)
    $input.on('keydown', function (e) {
        if (e.key === 'Enter') {
            var first = $results.find('.gs-item').first();
            if (first.length) {
                window.location.href = first.attr('href');
            }
        }
    });
})();
