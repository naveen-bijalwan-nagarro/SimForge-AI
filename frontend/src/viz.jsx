import React, { useEffect, useMemo, useRef } from "react";
import * as echarts from "echarts";
import cytoscape from "cytoscape";
import dagre from "cytoscape-dagre";

cytoscape.use(dagre);

export const healthColor = (h) =>
  h < 40 ? "#e5484d" : h < 75 ? "#e2a336" : "#35a37b";
const palette = ["#7761db", "#2f9e8f", "#e2a336", "#e5484d", "#4a8fe7", "#9b6b3c", "#8a90a6", "#c05dbd"];

/* ------------------------------------------------------------------ ECharts */
export function EChart({ option, height = 260, label = "Chart" }) {
  const ref = useRef(null);
  const chart = useRef(null);
  useEffect(() => {
    chart.current = echarts.init(ref.current, null, { renderer: "canvas" });
    const ro = new ResizeObserver(() => chart.current?.resize());
    ro.observe(ref.current);
    return () => {
      ro.disconnect();
      chart.current?.dispose();
    };
  }, []);
  useEffect(() => {
    chart.current?.setOption(
      {
        color: palette,
        textStyle: { fontFamily: "Inter, Segoe UI, Arial" },
        animationDuration: 450,
        grid: { left: 48, right: 18, top: 34, bottom: 34 },
        tooltip: { trigger: "axis" },
        ...option,
      },
      true,
    );
  }, [option]);
  return (
    <div
      ref={ref}
      className="echart"
      style={{ height, width: "100%" }}
      role="img"
      aria-label={label}
    />
  );
}

export const lineOption = (xs, series, { yName = "", markX } = {}) => ({
  legend: { top: 0, type: "scroll" },
  xAxis: { type: "category", data: xs, boundaryGap: false },
  yAxis: { type: "value", name: yName, nameTextStyle: { align: "left" } },
  series: series.map((s) => ({
    type: "line",
    smooth: true,
    showSymbol: false,
    ...s,
    ...(markX != null
      ? {
          markLine: {
            symbol: "none",
            label: { formatter: "onset" },
            lineStyle: { color: "#e5484d", type: "dashed" },
            data: [{ xAxis: String(markX) }],
          },
        }
      : {}),
  })),
});

/* ------------------------------------------------------------------ Cytoscape */
export function CyGraph({ nodes, edges, height = 380, onSelect, layout = "dagre", rankDir = "LR", label = "Graph" }) {
  const ref = useRef(null);
  const cy = useRef(null);
  const data = useMemo(
    () => [
      ...nodes.map((n) => ({ data: { ...n, id: String(n.id) } })),
      ...edges
        .filter((e) => nodes.some((n) => n.id === e.source) && nodes.some((n) => n.id === e.target))
        .map((e, i) => ({ data: { id: `e${i}`, ...e, source: String(e.source), target: String(e.target) } })),
    ],
    [nodes, edges],
  );
  useEffect(() => {
    cy.current = cytoscape({
      container: ref.current,
      elements: data,
      wheelSensitivity: 0.3,
      style: [
        {
          selector: "node",
          style: {
            label: "data(label)",
            "background-color": "data(color)",
            width: "data(size)",
            height: "data(size)",
            "font-size": 10,
            color: "#29314e",
            "text-valign": "bottom",
            "text-margin-y": 5,
            "text-wrap": "wrap",
            "text-max-width": 110,
            "border-width": 2,
            "border-color": "#ffffff",
          },
        },
        {
          selector: "edge",
          style: {
            width: 1.6,
            "line-color": "data(color)",
            "target-arrow-color": "data(color)",
            "target-arrow-shape": "triangle",
            "curve-style": "bezier",
            label: "data(label)",
            "font-size": 8,
            color: "#8a90a6",
            "text-rotation": "autorotate",
          },
        },
        { selector: "node[shape]", style: { shape: "data(shape)" } },
        { selector: ":selected", style: { "border-color": "#7761db", "border-width": 4 } },
      ],
      layout:
        layout === "dagre"
          ? { name: "dagre", rankDir, nodeSep: 26, rankSep: rankDir === "TB" ? 34 : 70, padding: 12 }
          : { name: "cose", animate: false, padding: 16, nodeRepulsion: 9000, idealEdgeLength: 70, nodeOverlap: 12, randomize: false, componentSpacing: 60 },
    });
    cy.current.on("tap", "node", (e) => onSelect?.(e.target.data()));
    return () => cy.current?.destroy();
  }, [data, layout, rankDir]);
  return <div ref={ref} className="cy-graph" style={{ height }} role="img" aria-label={label} />;
}

