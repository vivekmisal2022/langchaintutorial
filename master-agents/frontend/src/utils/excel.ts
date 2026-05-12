/**
 * Excel export utility using SheetJS (xlsx).
 */
import * as XLSX from 'xlsx';
import type { TableData } from '../types';

/**
 * Export table data to Excel file.
 */
export async function exportToExcel(data: TableData, filename: string = 'export'): Promise<void> {
  try {
    // Create a new workbook
    const workbook = XLSX.utils.book_new();

    // Convert data to worksheet format
    const worksheetData = [
      // Header row
      data.columns.map((col) => col.header),
      // Data rows
      ...data.rows.map((row) =>
        data.columns.map((col) => row[col.accessor] ?? '')
      ),
    ];

    // Create worksheet
    const worksheet = XLSX.utils.aoa_to_sheet(worksheetData);

    // Auto-size columns
    const maxWidths = data.columns.map((col) => {
      const headerLength = col.header.length;
      const maxDataLength = Math.max(
        ...data.rows.map((row) => {
          const value = row[col.accessor];
          return value ? String(value).length : 0;
        })
      );
      return Math.max(headerLength, maxDataLength, 10);
    });

    worksheet['!cols'] = maxWidths.map((width) => ({ wch: width }));

    // Add worksheet to workbook
    XLSX.utils.book_append_sheet(workbook, worksheet, 'Data');

    // Generate filename with timestamp
    const timestamp = new Date().toISOString().slice(0, 19).replace(/:/g, '-');
    const fullFilename = `${filename}_${timestamp}.xlsx`;

    // Write file
    XLSX.writeFile(workbook, fullFilename);
  } catch (error) {
    console.error('Excel export error:', error);
    throw new Error('Failed to export to Excel');
  }
}
