// DIARY_TOTALS_V1: подпись под итогом дня.
//
// В карточке крупно стоит факт, план — мелким серым. На только что
// импортированном плане факт честно нулевой (ничего не отмечено съеденным), и
// строка «0 / 747 ккал» читается как поломка. Одна фраза объясняет, почему нули
// и что с этим делать.

export interface DayBucket {
  calories: number;
}

export const dayTotalsHint = (planned: DayBucket, actual: DayBucket): string => {
  if (planned.calories > 0 && actual.calories === 0) {
    return 'План на день есть, но ничего не отмечено съеденным — отмечайте приёмы галочкой, и появится факт.';
  }
  if (planned.calories === 0 && actual.calories === 0) {
    return 'За этот день пока ничего нет: заполните из меню или добавьте приём.';
  }
  return '';
};
