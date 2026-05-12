/**
 * Table display component for rendering data tables from AI responses.
 */
import { useState, useMemo } from 'react';
import { AnalyticalTable, Button, FlexBox, Title } from '@ui5/webcomponents-react';
import '@ui5/webcomponents-icons/dist/excel-attachment.js';
import type { TableData } from '../types';
import { exportToExcel } from '../utils/excel';

interface TableDisplayProps {
  data: TableData;
}

export function TableDisplay({ data }: TableDisplayProps) {
  const [isExporting, setIsExporting] = useState(false);

  // Convert table data to AnalyticalTable format with proper configuration
  // Memoize columns to prevent unnecessary re-renders
  const columns = useMemo(
    () =>
      data.columns.map((col) => ({
        Header: col.header,
        accessor: col.accessor,
        hAlign: 'Begin' as const,
        width: 150,
      })),
    [data.columns]
  );

  const handleExport = async () => {
    setIsExporting(true);
    try {
      await exportToExcel(data, 'data-export');
    } catch (error) {
      console.error('Export failed:', error);
    } finally {
      setIsExporting(false);
    }
  };

  return (
    <FlexBox
      direction="Column"
      style={{
        gap: '0.5rem',
        marginTop: '0.5rem',
        maxWidth: '100%',
      }}
    >
      {/* Table Header with Export Button */}
      <FlexBox justifyContent="SpaceBetween" alignItems="Center">
        <Title level="H5">Data Table ({data.rows.length} rows)</Title>
        <Button
          icon="excel-attachment"
          onClick={handleExport}
          disabled={isExporting}
          tooltip="Export to Excel"
        >
          {isExporting ? 'Exporting...' : 'Export'}
        </Button>
      </FlexBox>

      {/* Analytical Table */}
      <AnalyticalTable
        columns={columns}
        data={data.rows}
        filterable
        sortable
        visibleRows={10}
        minRows={5}
        scaleWidthMode="Grow"
        onSort={(e) => {
          console.log('Sort event:', e.detail);
        }}
        onFilter={(e) => {
          console.log('Filter event:', e.filters);
        }}
        style={{
          width: '100%',
          maxHeight: '400px',
        }}
      />
    </FlexBox>
  );
}
