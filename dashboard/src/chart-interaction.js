// Freeze the rendered datum, not the distance between the axis's display labels.
// Tick density is a readability decision and says nothing about selection scope.
export function chartPointSelection(wrapper, target, readStyle = globalThis.getComputedStyle) {
  const wrapperBounds = wrapper.getBoundingClientRect();
  if (!wrapperBounds.width || !wrapperBounds.height) return null;
  const explicitMark = target?.closest?.(".recharts-dot");
  const explicitDot = explicitMark?.matches?.("circle") ? explicitMark : explicitMark?.querySelector?.("circle");
  const activeDots = [...wrapper.querySelectorAll(".recharts-active-dot circle")];
  const cursor = wrapper.querySelector(".recharts-tooltip-cursor");
  const cursorBounds = cursor?.getBoundingClientRect();
  const dotBounds = (explicitDot ?? activeDots[0])?.getBoundingClientRect();
  const thinCursor = cursorBounds?.height > 2 && cursorBounds.width <= 2;
  const center = explicitDot && dotBounds?.width > 0 ? dotBounds.left + dotBounds.width / 2
    : thinCursor ? cursorBounds.left + cursorBounds.width / 2
      : dotBounds?.width > 0 ? dotBounds.left + dotBounds.width / 2 : null;
  if (!Number.isFinite(center)) return null;
  const plot = thinCursor ? cursorBounds : wrapper.querySelector(".recharts-cartesian-grid")?.getBoundingClientRect() ?? wrapperBounds;
  if (!(plot.height > 0)) return null;
  const scaleX = (wrapper.offsetWidth || wrapperBounds.width) / wrapperBounds.width;
  const scaleY = (wrapper.offsetHeight || wrapperBounds.height) / wrapperBounds.height;
  const left = (center - wrapperBounds.left) * scaleX - 0.5;
  const top = (plot.top - wrapperBounds.top) * scaleY;
  const activeAtCenter = activeDots.filter(dot => {
    const bounds = dot.getBoundingClientRect();
    return Math.abs(bounds.left + bounds.width / 2 - center) <= 2;
  });
  const dots = activeAtCenter.length ? activeAtCenter : explicitDot ? [explicitDot] : [];
  const points = dots.flatMap(dot => {
    const bounds = dot.getBoundingClientRect();
    const x = bounds.left + bounds.width / 2;
    if (!bounds.width || !bounds.height || Math.abs(x - center) > 2) return [];
    const style = readStyle?.(dot);
    return [{ x: (x - wrapperBounds.left) * scaleX - left,
      y: (bounds.top + bounds.height / 2 - wrapperBounds.top) * scaleY - top,
      radius: bounds.width * scaleX / 2,
      fill: style?.fill || "var(--chart-1)", stroke: style?.stroke || "var(--surface)",
      strokeWidth: Number.parseFloat(style?.strokeWidth) || 0,
      opacity: style?.opacity || 1, fillOpacity: style?.fillOpacity || 1 }];
  });
  return { kind: "region", element: wrapper, left, top, width: 1, height: plot.height * scaleY,
    selectionType: "point", points, cursorStroke: cursor ? readStyle?.(cursor)?.stroke : "var(--border)" };
}

export function pinnedChartCardPosition(anchor, card, viewport, padding = 12) {
  const width = Math.min(card.width, Math.max(0, viewport.width - 2 * padding));
  const left = Math.max(padding, Math.min(anchor.x, viewport.width - width - padding));
  const top = Math.max(padding, Math.min(anchor.y, Math.max(padding, viewport.height - 80)));
  return { left, top, width, maxHeight: Math.max(0, viewport.height - top - padding) };
}

export function chartMarkTooltipPosition(mark, card, viewport, padding = 12, gap = 8, pointer) {
  if (Number.isFinite(pointer?.x) && Number.isFinite(pointer?.y)) {
    if (pointer.type === "touch") {
      const clearance = Math.max(24, gap + 16);
      const above = pointer.y - clearance - card.height;
      const below = pointer.y + clearance;
      const top = above >= padding ? above : below + card.height <= viewport.height - padding ? below
        : Math.max(padding, Math.min(above, viewport.height - card.height - padding));
      return { left: Math.max(padding, Math.min(pointer.x - card.width / 2,
        viewport.width - card.width - padding)), top };
    }
    const x = pointer.x + gap + card.width <= viewport.width - padding ? pointer.x + gap : pointer.x - gap - card.width;
    const above = pointer.y - gap - card.height;
    const y = pointer.y + gap + card.height <= viewport.height - padding ? pointer.y + gap
      : above >= padding ? above : viewport.height - card.height - padding;
    return { left: Math.max(padding, Math.min(x, viewport.width - card.width - padding)),
      top: Math.max(padding, Math.min(y, viewport.height - card.height - padding)) };
  }
  const left = Math.max(padding, Math.min(mark.left + mark.width / 2 - card.width / 2, viewport.width - card.width - padding));
  const above = mark.top - gap - card.height;
  const top = Math.max(padding, Math.min(above >= padding ? above : mark.bottom + gap, viewport.height - card.height - padding));
  return { left, top };
}

// Recharts' public Tooltip.position is relative to its chart, including CSS-scaled previews.
export function chartPointerTooltipPosition(bounds, size, card, viewport, pointer) {
  const position = chartMarkTooltipPosition(bounds, card, viewport, 12, 8, pointer);
  return { x: (position.left - bounds.left) * (size.width / bounds.width || 1),
    y: (position.top - bounds.top) * (size.height / bounds.height || 1) };
}

export function resolveChartAnchor(source) {
  if (source?.hoverCard?.element?.isConnected) {
    const bounds = source.hoverCard.element.getBoundingClientRect();
    return { x: bounds.left + source.hoverCard.left, y: bounds.top + source.hoverCard.top, bottom: bounds.top + source.hoverCard.top + source.hoverCard.height };
  }
  if (source?.kind === "region" && source.element?.isConnected) {
    const bounds = source.element.getBoundingClientRect();
    return {
      x: bounds.left + source.left + source.width / 2,
      y: bounds.top + source.top,
      bottom: bounds.top + source.top + source.height,
    };
  }
  if (source?.kind === "element" && source.element?.isConnected) {
    const bounds = source.element.getBoundingClientRect();
    const y = bounds.top + source.yOffset;
    return { x: bounds.left + (source.xOffset ?? bounds.width / 2), y, bottom: y };
  }
  if (source?.kind === "range") {
    const bounds = source.range.getBoundingClientRect();
    if (bounds.width || bounds.height)
      return {
        x: bounds.left + bounds.width / 2,
        y: bounds.top,
        bottom: bounds.bottom,
      };
  }
  return null;
}

function axisBand(wrapper, axis) {
  const selector =
    axis === "x"
      ? ".recharts-xAxis-tick-labels .recharts-cartesian-axis-tick-label"
      : ".recharts-yAxis-tick-labels .recharts-cartesian-axis-tick-label";
  const centers = [...wrapper.querySelectorAll(selector)]
    .map((tick) => {
      const bounds = tick.getBoundingClientRect();
      return axis === "x" ? bounds.left + bounds.width / 2 : bounds.top + bounds.height / 2;
    })
    .filter(Number.isFinite)
    .sort((left, right) => left - right);
  const gaps = centers
    .slice(1)
    .map((center, index) => center - centers[index])
    .filter((gap) => gap > 2);
  if (!gaps.length) return null;
  const size = Math.min(...gaps);
  return {
    centers,
    size,
    start: centers[0] - size / 2,
    end: centers.at(-1) + size / 2,
  };
}

export function chartRegionSource(target, event, chartType) {
  const rankedRow = target?.closest?.(".chart-ranked-list-row, .chart-funnel-stage, [data-chart-mark]");
  if (rankedRow) {
    const bounds = rankedRow.getBoundingClientRect();
    if (!bounds.width || !bounds.height) return null;
    return {
      kind: "region",
      element: rankedRow,
      left: 0,
      top: 0,
      width: bounds.width,
      height: bounds.height,
      markElement: rankedRow,
      selectionType: "mark",
      renderOverlay: !rankedRow.hasAttribute("data-chart-mark"),
    };
  }
  const wrapper = target?.closest?.(".recharts-wrapper");
  if (!wrapper) return null;
  const wrapperBounds = wrapper.getBoundingClientRect();
  const cursor = wrapper.querySelector(".recharts-tooltip-cursor");
  const barMark = target?.closest?.(".recharts-rectangle");
  if (!barMark && ["line", "sparkline", "area", "stackedArea"].includes(chartType)) {
    return chartPointSelection(wrapper, target);
  }
  const lineMark =
    target?.closest?.(".recharts-dot, .recharts-curve") ??
    wrapper.querySelector(".recharts-active-dot circle, .recharts-active-dot");
  const markElement = barMark ?? lineMark;
  const targetBounds = markElement?.getBoundingClientRect?.() ?? target?.getBoundingClientRect?.();
  const cursorBounds = cursor?.getBoundingClientRect?.();
  let bounds = barMark
    ? targetBounds
    : cursorBounds?.width > 2 && cursorBounds?.height > 2
      ? cursorBounds
      : targetBounds;
  if (lineMark && !(cursorBounds?.height > 2 && cursorBounds.width <= 2)) {
    const band = axisBand(wrapper, "x");
    const plotBounds = wrapper.querySelector(".recharts-cartesian-grid")?.getBoundingClientRect();
    const pointerX = event?.clientX ?? targetBounds?.left + targetBounds?.width / 2;
    const center = band?.centers.length
      ? band.centers.reduce(
          (nearest, candidate) => (Math.abs(candidate - pointerX) < Math.abs(nearest - pointerX) ? candidate : nearest),
          band.centers[0],
        )
      : null;
    if (band && plotBounds && Number.isFinite(center)) {
      const left = Math.max(band.start, center - band.size / 2);
      const right = Math.min(band.end, center + band.size / 2);
      bounds = {
        left,
        top: plotBounds.top,
        width: right - left,
        height: plotBounds.height,
      };
    }
  } else if (cursorBounds?.height > 2 && cursorBounds.width <= 2) {
    const band = axisBand(wrapper, "x");
    const center = cursorBounds.left + cursorBounds.width / 2;
    const width = band?.size ?? Math.max(targetBounds?.width ?? 0, 32);
    const left = Math.max(band?.start ?? wrapperBounds.left, center - width / 2);
    const right = Math.min(band?.end ?? wrapperBounds.right, center + width / 2);
    bounds = {
      left,
      top: cursorBounds.top,
      width: right - left,
      height: cursorBounds.height,
    };
  } else if (cursorBounds?.width > 2 && cursorBounds.height <= 2) {
    const band = axisBand(wrapper, "y");
    const center = cursorBounds.top + cursorBounds.height / 2;
    const height = band?.size ?? Math.max(targetBounds?.height ?? 0, 32);
    const top = Math.max(band?.start ?? wrapperBounds.top, center - height / 2);
    const bottom = Math.min(band?.end ?? wrapperBounds.bottom, center + height / 2);
    bounds = {
      left: cursorBounds.left,
      top,
      width: cursorBounds.width,
      height: bottom - top,
    };
  }
  if (!bounds?.width || !bounds?.height) return null;
  return {
    kind: "region",
    element: wrapper,
    left: bounds.left - wrapperBounds.left,
    top: bounds.top - wrapperBounds.top,
    width: bounds.width,
    height: bounds.height,
    markElement,
    selectionType: barMark ? "mark" : "band",
  };
}

export function chartSectionSource(target) {
  const wrapper = target?.closest?.(".recharts-wrapper, .chart-funnel");
  if (!wrapper) return null;
  const bounds = wrapper.getBoundingClientRect();
  if (!bounds.width || !bounds.height) return null;
  return {
    kind: "region",
    element: wrapper,
    left: 0,
    top: 0,
    width: bounds.width,
    height: bounds.height,
    selectionType: "band",
  };
}

export function hasSelectedChartData(context) {
  return Boolean(context?.row && typeof context.row === "object" && !Array.isArray(context.row)
    && Object.keys(context.row).length) || context?.value !== undefined;
}

export function selectedChartData(context) {
  const data = context?.row && typeof context.row === "object" && !Array.isArray(context.row)
    ? context.row
    : Object.fromEntries(["label", "series", "value"].filter(key => context?.[key] !== undefined)
      .map(key => [key, context[key]]));
  return JSON.stringify(data, null, 2);
}
