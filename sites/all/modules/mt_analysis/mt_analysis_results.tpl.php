<?php
/**
 * @file
 * Default theme implementation for mt_anlysis_results
 */
?>

<div class='mt_analysis_results' style="h2 {text-decoration:underline;}">

  <?php if ($results == NULL): ?>

    <p>Before viewing MT task results, please first load HITs and assignments, and then issue the 'compute results' command.</p>

  <?php else: ?>

    <h2>Basic Statistics</h2>
    <ul>
      <li>Total HITs: <?php echo $results['total_hits']; ?></li>
      <li>Total allowed assignments: <?php echo $results['total_max_assignments']; ?></li>
      <li>Finished assignments: <?php echo $results['total_assignments'] .' ('. number_format(100 * $results['total_assignments']/$results['total_max_assignments']) .'%)'; ?></li>
      <li>Total workers: <?php echo $results['total_workers']; ?></li>
      <li>Answers summary: <?php echo json_encode($results['answers_summary']); ?></li>
    </ul>

    <h2>Inter-rater agreement</h2>
    <p><a href="http://en.wikipedia.org/wiki/Fleiss'_kappa">Fleiss' Kappa</a>: <strong><?php echo number_format($results['fleiss'], 3); ?></strong> (from <?php echo $results['fleiss_valid_hits']; ?> valid HITs).</p>

    <h2>CSV results</h2>
    <p>Download MT task results based on majority votes: <a href="<?php echo $results['csv_majority']; ?>">click here</a>.</p>
    <p><em>Note</em>: If CSV file has encoding errors, please use the JSON output data['results_majority'] instead.</p>

    <h2>JSON results</h2>
    <p>For JSON results, please visit <a href="<?php echo $results['json_url']; ?>">this URL</a>.</p>

    <p><em>Last updated: <?php echo format_date($results['updated']); ?></em></p>

  <?php endif; ?>

</div>

