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
        $row['data'] = $row['name'] .': '. $row['points']; // for theme_item_list()
        if ($row['bonus'] > 0) {
          $bonus_str = money_format('%!.2n', $row['bonus']);
          $row['data'] .= " (\$$bonus_str)";
          $row['style'] = 'color:red;';
        }
      }
      print theme('item_list', array('items' => $rows, 'type' => 'ol'));
    ?>
  <?php endif; ?>
</div>
