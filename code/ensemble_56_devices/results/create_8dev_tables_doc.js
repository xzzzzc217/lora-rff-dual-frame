const fs = require("fs");
const {
  Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell,
  AlignmentType, BorderStyle, WidthType, ShadingType, HeadingLevel
} = require("docx");

// Data from results_8dev_ablation.json
const table2Data = [
  { name: "连续双帧差分相位+CFO（Base）", XGBoost: 0.9938, RF: 0.9981, SVM: 0.9800, KNN: 0.8186, Ensemble: 0.9971, Max: 0.9981 },
  { name: "连续双帧差分相位+CFO 均值", XGBoost: 0.9947, RF: 0.9957, SVM: 0.9499, KNN: 0.7766, Ensemble: 0.9943, Max: 0.9957 },
  { name: "只用CFO特征（连续双帧下的）", XGBoost: 0.9938, RF: 0.9943, SVM: 0.9990, KNN: 0.9967, Ensemble: 0.9976, Max: 0.9990 },
  { name: "只用RSSI特征（连续双帧下的）", XGBoost: 0.5255, RF: 0.5365, SVM: 0.5919, KNN: 0.5537, Ensemble: 0.5728, Max: 0.5919 },
  { name: "只用IQ特征（连续双帧下的）", XGBoost: 0.5084, RF: 0.5093, SVM: 0.5313, KNN: 0.5184, Ensemble: 0.5294, Max: 0.5313 },
  { name: "只用单帧相位特征", XGBoost: 0.3399, RF: 0.3637, SVM: 0.2969, KNN: 0.3098, Ensemble: 0.3537, Max: 0.3637 },
  { name: "只用双帧相位特征", XGBoost: 0.4148, RF: 0.4444, SVM: 0.3814, KNN: 0.3604, Ensemble: 0.4220, Max: 0.4444 },
  { name: "双帧相位特征+CFO 特征", XGBoost: 0.9938, RF: 0.9981, SVM: 0.9900, KNN: 0.8988, Ensemble: 0.9986, Max: 0.9986 },
  { name: "单帧相位特征+CFO 特征", XGBoost: 0.9938, RF: 0.9971, SVM: 0.9976, KNN: 0.9647, Ensemble: 0.9981, Max: 0.9981 },
  { name: "Base+STFT", XGBoost: 0.9909, RF: 0.9971, SVM: 0.9962, KNN: 0.9394, Ensemble: 0.9990, Max: 0.9990 },
  { name: "Base+EMD", XGBoost: 0.9279, RF: 0.9289, SVM: 0.8807, KNN: 0.7341, Ensemble: 0.8878, Max: 0.9289 },
];

const table3Data = [
  { name: "连续双帧差分相位+CFO（Base）", XGBoost: 0.7849, RF: 0.9304, SVM: 0.9017, KNN: 0.6174, Ensemble: 0.9596, Max: 0.9596 },
  { name: "连续双帧差分相位+CFO 均值", XGBoost: 0.9546, RF: 0.9529, SVM: 0.8509, KNN: 0.5370, Ensemble: 0.9502, Max: 0.9546 },
  { name: "只用CFO特征（连续双帧下的）", XGBoost: 0.8352, RF: 0.9542, SVM: 0.9524, KNN: 0.9470, Ensemble: 0.9578, Max: 0.9578 },
  { name: "只用RSSI特征（连续双帧下的）", XGBoost: 0.1599, RF: 0.1437, SVM: 0.1774, KNN: 0.1504, Ensemble: 0.1594, Max: 0.1774 },
  { name: "只用IQ特征（连续双帧下的）", XGBoost: 0.1756, RF: 0.1670, SVM: 0.1935, KNN: 0.2093, Ensemble: 0.2043, Max: 0.2093 },
  { name: "只用单帧相位特征", XGBoost: 0.1392, RF: 0.1311, SVM: 0.1688, KNN: 0.1626, Ensemble: 0.1522, Max: 0.1688 },
  { name: "只用双帧相位特征", XGBoost: 0.1464, RF: 0.1590, SVM: 0.1841, KNN: 0.1711, Ensemble: 0.1774, Max: 0.1841 },
  { name: "双帧相位特征+CFO 特征", XGBoost: 0.8348, RF: 0.9569, SVM: 0.9196, KNN: 0.7009, Ensemble: 0.9663, Max: 0.9663 },
  { name: "单帧相位特征+CFO 特征", XGBoost: 0.9506, RF: 0.9573, SVM: 0.9515, KNN: 0.8698, Ensemble: 0.9663, Max: 0.9663 },
  { name: "Base+STFT", XGBoost: 0.5824, RF: 0.3817, SVM: 0.3718, KNN: 0.3107, Ensemble: 0.4854, Max: 0.5824 },
  { name: "Base+EMD", XGBoost: 0.6354, RF: 0.8604, SVM: 0.6974, KNN: 0.4230, Ensemble: 0.8496, Max: 0.8604 },
];

const fmtPct = (v) => `${Math.round(v * 100)}%`;
const fmtPctDot = (v) => `${(v * 100).toFixed(1)}%`;

const headers = ["特征组合", "XGBoost", "随机森林", "SVM", "KNN", "集成学习", "最大正确率"];
const colWidths = [3200, 1100, 1100, 1000, 1000, 1100, 1100];
const tableWidth = colWidths.reduce((a, b) => a + b, 0);

const thinBorder = { style: BorderStyle.SINGLE, size: 1, color: "999999" };
const borders = { top: thinBorder, bottom: thinBorder, left: thinBorder, right: thinBorder };

function makeHeaderCell(text, width) {
  return new TableCell({
    borders,
    width: { size: width, type: WidthType.DXA },
    shading: { fill: "2E5A3E", type: ShadingType.CLEAR },
    verticalAlign: "center",
    margins: { top: 60, bottom: 60, left: 80, right: 80 },
    children: [
      new Paragraph({
        alignment: AlignmentType.CENTER,
        spacing: { before: 0, after: 0 },
        children: [
          new TextRun({ text, bold: true, color: "FFFFFF", font: "宋体", size: 21 }),
        ],
      }),
    ],
  });
}

function makeDataCell(text, width, isBold, isEnsemble) {
  const shading = isEnsemble ? { fill: "E8F5E9", type: ShadingType.CLEAR } : undefined;
  return new TableCell({
    borders,
    width: { size: width, type: WidthType.DXA },
    shading,
    verticalAlign: "center",
    margins: { top: 50, bottom: 50, left: 80, right: 80 },
    children: [
      new Paragraph({
        alignment: AlignmentType.CENTER,
        spacing: { before: 0, after: 0 },
        children: [
          new TextRun({ text, bold: isBold, font: "宋体", size: 21 }),
        ],
      }),
    ],
  });
}

function makeNameCell(text, width, isBold) {
  return new TableCell({
    borders,
    width: { size: width, type: WidthType.DXA },
    verticalAlign: "center",
    margins: { top: 50, bottom: 50, left: 100, right: 80 },
    children: [
      new Paragraph({
        alignment: AlignmentType.LEFT,
        spacing: { before: 0, after: 0 },
        children: [
          new TextRun({ text, bold: isBold, font: "宋体", size: 21 }),
        ],
      }),
    ],
  });
}

function buildTable(data) {
  // Header row
  const headerRow = new TableRow({
    children: headers.map((h, i) => makeHeaderCell(h, colWidths[i])),
  });

  // Data rows
  const dataRows = data.map((row) => {
    const vals = [row.XGBoost, row.RF, row.SVM, row.KNN, row.Ensemble, row.Max];
    const maxVal = row.Max;

    return new TableRow({
      children: [
        makeNameCell(row.name, colWidths[0], false),
        ...vals.map((v, i) => {
          const isBold = Math.abs(v - maxVal) < 0.0001;
          const isEnsemble = i === 4; // "集成学习" column
          return makeDataCell(fmtPctDot(v), colWidths[i + 1], isBold, isEnsemble);
        }),
      ],
    });
  });

  return new Table({
    width: { size: tableWidth, type: WidthType.DXA },
    columnWidths: colWidths,
    rows: [headerRow, ...dataRows],
  });
}

const doc = new Document({
  styles: {
    default: {
      document: { run: { font: "宋体", size: 24 } },
    },
  },
  sections: [
    {
      properties: {
        page: {
          size: { width: 11906, height: 16838 }, // A4
          margin: { top: 1440, right: 1200, bottom: 1440, left: 1200 },
        },
      },
      children: [
        // Table 2 title
        new Paragraph({
          alignment: AlignmentType.CENTER,
          spacing: { before: 200, after: 300 },
          children: [
            new TextRun({
              text: "表2  训练集和测试集在同一天的识别结果",
              bold: true,
              font: "黑体",
              size: 24,
            }),
          ],
        }),

        buildTable(table2Data),

        // Spacing between tables
        new Paragraph({ spacing: { before: 600, after: 0 }, children: [] }),

        // Table 3 title
        new Paragraph({
          alignment: AlignmentType.CENTER,
          spacing: { before: 200, after: 300 },
          children: [
            new TextRun({
              text: "表3  训练集和测试集在不同天的识别结果",
              bold: true,
              font: "黑体",
              size: 24,
            }),
          ],
        }),

        buildTable(table3Data),
      ],
    },
  ],
});

const outputPath = "C:\\Users\\21398\\Desktop\\sophomore\\SRTP\\code\\ensemble_56_devices\\results\\8台设备消融实验结果.docx";
Packer.toBuffer(doc).then((buffer) => {
  fs.writeFileSync(outputPath, buffer);
  console.log("Created: " + outputPath);
});
