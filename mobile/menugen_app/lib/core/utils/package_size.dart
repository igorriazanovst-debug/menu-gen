// MG_DIARYSCAN: размер упаковки из строки вроде «930мл» или «4.5г x 4 шт».
//
// В дневник еду вносят целыми упаковками: выпил бутылку йогурта, съел пачку
// чипсов. Справочник сети хранит фасовку строкой рядом с товаром, поэтому
// количество подставляется сразу — поправить проще, чем набрать заново.
//
// Миллилитры считаем граммами: для напитков разница в пределах процентов, а
// иначе пересчитывать пришлось бы человеку.

const Map<String, double> _multipliers = {
  'г': 1,
  'гр': 1,
  'g': 1,
  'мл': 1,
  'ml': 1,
  'кг': 1000,
  'kg': 1000,
  'л': 1000,
  'l': 1000,
};

final RegExp _sizeRe = RegExp(r'(\d+(?:\.\d+)?)\s*(кг|kg|мл|ml|гр|г|g|л|l)(?![а-яёa-z])');
// Множитель бывает и кириллической «х» — на этикетках их не различают.
final RegExp _packsRe = RegExp(r'^\s*[xх×*]\s*(\d+)');

/// Граммы из строки фасовки. null — если размер не читается («упак», «шт»).
int? packageGrams(String? text) {
  final raw = (text ?? '').toLowerCase().replaceAll(',', '.');
  if (raw.isEmpty) return null;

  final m = _sizeRe.firstMatch(raw);
  if (m == null) return null;

  final amount = (double.tryParse(m.group(1)!) ?? 0) * (_multipliers[m.group(2)!] ?? 1);
  if (amount <= 0) return null;

  final packs = _packsRe.firstMatch(raw.substring(m.end));
  final total = packs != null ? amount * (int.tryParse(packs.group(1)!) ?? 1) : amount;

  return (total > 0 && total <= 20000) ? total.round() : null;
}
