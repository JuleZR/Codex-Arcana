(function ($) {
    "use strict";

    var EMPTY_VALUE = "-";

    function setReadonlyValue($row, fieldName, value) {
        var $cell = $row.find("td.field-" + fieldName);
        if (!$cell.length) {
            return;
        }
        $cell.text(value == null ? EMPTY_VALUE : String(value));
    }

    function clearReadonlyValues($row) {
        setReadonlyValue($row, "trait_min_level", EMPTY_VALUE);
        setReadonlyValue($row, "trait_max_level", EMPTY_VALUE);
        setReadonlyValue($row, "trait_points_per_level", EMPTY_VALUE);
    }

    function buildMetaUrl(template, traitId) {
        return template.replace(/0\/?$/, String(traitId) + "/");
    }

    function updateTraitMetaForRow($row) {
        var $select = $row.find("select[name$='-trait']");
        if (!$select.length) {
            return;
        }

        var traitId = $select.val();
        if (!traitId) {
            clearReadonlyValues($row);
            return;
        }

        var urlTemplate = $select.attr("data-trait-meta-url-template");
        if (!urlTemplate) {
            clearReadonlyValues($row);
            return;
        }

        var url = buildMetaUrl(urlTemplate, traitId);

        fetch(url, {
            credentials: "same-origin",
            headers: { "X-Requested-With": "XMLHttpRequest" }
        })
            .then(function (response) {
                if (!response.ok) {
                    throw new Error("Trait metadata request failed");
                }
                return response.json();
            })
            .then(function (data) {
                setReadonlyValue($row, "trait_min_level", data.min_level);
                setReadonlyValue($row, "trait_max_level", data.max_level);
                setReadonlyValue($row, "trait_points_per_level", data.points_per_level);
            })
            .catch(function () {
                clearReadonlyValues($row);
            });
    }

    $(document).on("change", "select[name$='-trait']", function () {
        updateTraitMetaForRow($(this).closest("tr"));
    });

    $(document).ready(function () {
        $("tr.form-row, tr.dynamic-charactertrait_set").each(function () {
            updateTraitMetaForRow($(this));
        });
    });

    $(document).on("formset:added", function (event, $row) {
        updateTraitMetaForRow($row);
    });
})(django.jQuery);
