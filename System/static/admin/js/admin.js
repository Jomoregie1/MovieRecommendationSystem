$(document).ready(function() {
    const noResultsRow = "<tr id='noResultsRow'><td colspan='7'>No results found</td></tr>";

    $("#searchInput").on("input", function() {
      const value = $(this).val().toLowerCase();
      let visibleRowCount = 0;

      $("tbody tr").each(function() {
        const emailCell = $(this).find("td:eq(5)");
        const shouldShow = emailCell.text().toLowerCase().indexOf(value) > -1;

        if (shouldShow) {
          visibleRowCount++;
        }

        $(this).toggle(shouldShow);
      });

      $("#noResultsRow").remove();

      if (visibleRowCount === 0) {
        $("tbody").append(noResultsRow);
      }
    });
  });