import 'package:flutter/material.dart';

/// MG_SKIN: перетаскиваемая «плавающая» кнопка-действие. Положение хранится
/// локально, по умолчанию — снизу справа; ограничивается границами области.
class DraggableActionButton extends StatefulWidget {
  final VoidCallback onPressed;
  final IconData icon;
  final String label;
  final double width;
  final double height;

  const DraggableActionButton({
    super.key,
    required this.onPressed,
    required this.icon,
    required this.label,
    this.width = 168,
    this.height = 46,
  });

  @override
  State<DraggableActionButton> createState() => _DraggableActionButtonState();
}

class _DraggableActionButtonState extends State<DraggableActionButton> {
  Offset? _pos; // top-left; null = дефолт (снизу справа)

  double _clamp(double v, double lo, double hi) =>
      v < lo ? lo : (v > hi ? hi : v);

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    final w = widget.width;
    final h = widget.height;
    return LayoutBuilder(
      builder: (context, c) {
        final maxX = c.maxWidth - w - 8;
        final maxY = c.maxHeight - h - 8;
        final hiX = maxX < 8 ? 8.0 : maxX;
        final hiY = maxY < 8 ? 8.0 : maxY;
        final base = _pos ?? Offset(c.maxWidth - w - 16, c.maxHeight - h - 16);
        final dx = _clamp(base.dx, 8, hiX);
        final dy = _clamp(base.dy, 8, hiY);
        return Stack(
          children: [
            Positioned(
              left: dx,
              top: dy,
              child: GestureDetector(
                onPanUpdate: (d) {
                  setState(() {
                    _pos = Offset(
                      _clamp(dx + d.delta.dx, 8, hiX),
                      _clamp(dy + d.delta.dy, 8, hiY),
                    );
                  });
                },
                child: Material(
                  color: cs.primary,
                  elevation: 4,
                  borderRadius: BorderRadius.circular(h / 2),
                  child: InkWell(
                    borderRadius: BorderRadius.circular(h / 2),
                    onTap: widget.onPressed,
                    child: SizedBox(
                      width: w,
                      height: h,
                      child: Row(
                        mainAxisAlignment: MainAxisAlignment.center,
                        children: [
                          Icon(widget.icon, color: Colors.white, size: 20),
                          const SizedBox(width: 8),
                          Text(
                            widget.label,
                            style: const TextStyle(
                              color: Colors.white,
                              fontWeight: FontWeight.w600,
                              fontSize: 15,
                            ),
                          ),
                        ],
                      ),
                    ),
                  ),
                ),
              ),
            ),
          ],
        );
      },
    );
  }
}
