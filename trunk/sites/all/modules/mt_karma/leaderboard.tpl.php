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
      setlocale(LC_MONETARY, 'en_US');
      foreach ($rows as &$row) {
        //$row['data'] = "<strong>{$row['name']}</strong>: {$row['points']}"; // for theme_item_list()
        $row['data'] = "<span class='name'>{$row['name']}</span>: <span class='points'>{$row['points']}</span>"; // for theme_item_list()
        if ($row['bonus'] > 0) {
          $bonus_str = money_format('%!.2n', $row['bonus']);
          $row['data'] .= " <span class='bonus'>(\$$bonus_str)</span>";
          $row['style'] = 'font-weight:bold;';
        }
        // remove extra attributes
        unset($row['name']);
        unset($row['points']);
        unset($row['bonus']);
      }
      print theme('item_list', array('items' => $rows, 'type' => 'ol'));
    ?>
  <?php endif; ?>
</div>
