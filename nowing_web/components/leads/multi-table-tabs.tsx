"use client";

import {
	Briefcase,
	Building,
	Check,
	Edit2,
	Home,
	Plus,
	Table as TableIcon,
	Trash2,
	Users,
	X,
} from "lucide-react";
import type React from "react";
import { useState } from "react";
import type { WorkspaceTable } from "@/contracts/types/workspace-table.types";

interface MultiTableTabsProps {
	tables: WorkspaceTable[];
	activeTableId: string | null;
	onSelectTable: (tableId: string | null) => void;
	onCreateTable: (name: string, icon: string) => Promise<void>;
	onUpdateTable: (tableId: string, name: string) => Promise<void>;
	onDeleteTable: (tableId: string) => Promise<void>;
}

const ICON_MAP: Record<string, React.ReactNode> = {
	table: <TableIcon className="w-3.5 h-3.5" />,
	home: <Home className="w-3.5 h-3.5 text-blue-400" />,
	briefcase: <Briefcase className="w-3.5 h-3.5 text-amber-400" />,
	building: <Building className="w-3.5 h-3.5 text-indigo-400" />,
	users: <Users className="w-3.5 h-3.5 text-emerald-400" />,
};

export const MultiTableTabs: React.FC<MultiTableTabsProps> = ({
	tables,
	activeTableId,
	onSelectTable,
	onCreateTable,
	onUpdateTable,
	onDeleteTable,
}) => {
	const [isAdding, setIsAdding] = useState<boolean>(false);
	const [newTableName, setNewTableName] = useState<string>("");
	const [newTableIcon, setNewTableIcon] = useState<string>("table");
	const [editingTableId, setEditingTableId] = useState<string | null>(null);
	const [editName, setEditName] = useState<string>("");

	const handleStartAdd = () => {
		setIsAdding(true);
		setNewTableName("");
		setNewTableIcon("table");
	};

	const handleConfirmAdd = async () => {
		if (!newTableName.trim()) return;
		await onCreateTable(newTableName.trim(), newTableIcon);
		setIsAdding(false);
		setNewTableName("");
	};

	const handleStartEdit = (table: WorkspaceTable, e: React.MouseEvent) => {
		e.stopPropagation();
		setEditingTableId(table.id);
		setEditName(table.name);
	};

	const handleConfirmEdit = async (tableId: string) => {
		if (editName.trim()) {
			await onUpdateTable(tableId, editName.trim());
		}
		setEditingTableId(null);
	};

	const handleDelete = async (tableId: string, e: React.MouseEvent) => {
		e.stopPropagation();
		if (window.confirm("Bạn có chắc muốn xóa tab bảng này? Dữ liệu lead vẫn được lưu trữ.")) {
			await onDeleteTable(tableId);
			if (activeTableId === tableId) {
				onSelectTable(null);
			}
		}
	};

	return (
		<div className="flex items-center gap-1.5 overflow-x-auto pb-1 scrollbar-thin scrollbar-thumb-zinc-800 border-b border-zinc-800/80">
			{/* All Leads (Default Tab) */}
			<button
				type="button"
				onClick={() => onSelectTable(null)}
				className={`flex items-center gap-2 px-3.5 py-2 text-xs font-medium rounded-t-lg transition-all border-t border-x ${
					activeTableId === null
						? "bg-zinc-900 border-zinc-700 text-emerald-400 border-b-zinc-900 z-10 shadow-sm"
						: "bg-zinc-950/60 border-transparent text-zinc-400 hover:text-zinc-200 hover:bg-zinc-900/50"
				}`}
			>
				<TableIcon className="w-3.5 h-3.5 text-zinc-400" />
				<span>Tất cả Leads (All Leads)</span>
			</button>

			{/* Custom Table Tabs */}
			{tables.map((table) => {
				const isActive = activeTableId === table.id;
				const isEditing = editingTableId === table.id;

				return (
					<div
						key={table.id}
						className={`group flex items-center gap-2 px-3.5 py-2 text-xs font-medium rounded-t-lg transition-all border-t border-x ${
							isActive
								? "bg-zinc-900 border-zinc-700 text-zinc-100 border-b-zinc-900 z-10 shadow-sm"
								: "bg-zinc-950/60 border-transparent text-zinc-400 hover:text-zinc-200 hover:bg-zinc-900/50"
						}`}
					>
						<button
							type="button"
							onClick={() => !isEditing && onSelectTable(table.id)}
							className="flex items-center gap-2 bg-transparent border-0 p-0 text-left text-xs font-medium text-inherit focus:outline-none"
						>
							{ICON_MAP[table.icon] || <TableIcon className="w-3.5 h-3.5" />}
							{!isEditing && <span className="truncate max-w-[140px]">{table.name}</span>}
						</button>

						{isEditing && (
							<div className="flex items-center gap-1">
								<input
									type="text"
									value={editName}
									onChange={(e) => setEditName(e.target.value)}
									className="px-1.5 py-0.5 text-xs rounded bg-zinc-950 border border-emerald-500 text-zinc-100 focus:outline-none w-28"
									onClick={(e) => e.stopPropagation()}
									onKeyDown={(e) => {
										if (e.key === "Enter") handleConfirmEdit(table.id);
										if (e.key === "Escape") setEditingTableId(null);
									}}
								/>
								<button
									type="button"
									onClick={(e) => {
										e.stopPropagation();
										handleConfirmEdit(table.id);
									}}
									className="p-0.5 text-emerald-400 hover:text-emerald-300"
								>
									<Check className="w-3.5 h-3.5" />
								</button>
								<button
									type="button"
									onClick={(e) => {
										e.stopPropagation();
										setEditingTableId(null);
									}}
									className="p-0.5 text-zinc-400 hover:text-zinc-300"
								>
									<X className="w-3.5 h-3.5" />
								</button>
							</div>
						)}

						{!isEditing && (
							<div className="flex items-center gap-0.5 opacity-0 group-hover:opacity-100 transition-opacity ml-1">
								<button
									type="button"
									onClick={(e) => handleStartEdit(table, e)}
									className="p-0.5 rounded text-zinc-500 hover:text-zinc-300 hover:bg-zinc-800"
									title="Đổi tên tab"
								>
									<Edit2 className="w-3 h-3" />
								</button>
								<button
									type="button"
									onClick={(e) => handleDelete(table.id, e)}
									className="p-0.5 rounded text-zinc-500 hover:text-rose-400 hover:bg-rose-500/10"
									title="Xóa tab"
								>
									<Trash2 className="w-3 h-3" />
								</button>
							</div>
						)}
					</div>
				);
			})}

			{/* Add New Table Button */}
			{isAdding ? (
				<div className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-zinc-900 border border-emerald-500/50 text-xs">
					<select
						value={newTableIcon}
						onChange={(e) => setNewTableIcon(e.target.value)}
						className="bg-zinc-950 text-zinc-300 text-xs border border-zinc-800 rounded px-1.5 py-0.5 focus:outline-none"
					>
						<option value="table">📊 Bảng</option>
						<option value="home">🏠 BĐS</option>
						<option value="briefcase">💼 Việc làm</option>
						<option value="building">🏛️ Doanh nghiệp</option>
						<option value="users">👥 Social</option>
					</select>
					<input
						type="text"
						value={newTableName}
						onChange={(e) => setNewTableName(e.target.value)}
						placeholder="Tên danh sách mới..."
						className="px-2 py-0.5 text-xs rounded bg-zinc-950 border border-zinc-800 text-zinc-100 focus:outline-none focus:border-emerald-500 w-32"
						onKeyDown={(e) => {
							if (e.key === "Enter") handleConfirmAdd();
							if (e.key === "Escape") setIsAdding(false);
						}}
					/>
					<button
						type="button"
						onClick={handleConfirmAdd}
						className="p-1 rounded bg-emerald-600 hover:bg-emerald-500 text-white transition-colors"
					>
						<Check className="w-3 h-3" />
					</button>
					<button
						type="button"
						onClick={() => setIsAdding(false)}
						className="p-1 rounded bg-zinc-800 hover:bg-zinc-700 text-zinc-400 transition-colors"
					>
						<X className="w-3 h-3" />
					</button>
				</div>
			) : (
				<button
					type="button"
					onClick={handleStartAdd}
					className="flex items-center gap-1 px-2.5 py-1.5 text-xs font-medium rounded-lg text-zinc-400 hover:text-emerald-400 hover:bg-zinc-900/60 border border-dashed border-zinc-800 hover:border-emerald-500/30 transition-colors"
				>
					<Plus className="w-3.5 h-3.5" />
					<span>Thêm bảng</span>
				</button>
			)}
		</div>
	);
};
