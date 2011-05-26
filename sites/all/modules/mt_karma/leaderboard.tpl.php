<?php
/**
 * @file
 * Default theme implementation for leaderboard
 */
?>
<div id="leaderboard" class="<?php print $classes; ?>"<?php print $attributes; ?>>
  <?php if (count($rows) == 0): ?>
    <p><?php print $empty; ?></p>
  <?php else: ?>
    <?php
      foreach ($rows as &$row) {
        $row['data'] = $row['name'] .': '. $row['points']; // for theme_item_list()
      }
      print theme('item_list', array('items' => $rows, 'type' => 'ol'));
    ?>
  <?php endif; ?>
</div>
