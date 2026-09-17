<script setup lang="ts">
import { computed, nextTick, onMounted, ref } from "vue"
import { ElMessage, ElMessageBox } from "element-plus"

import {
    bulkDeleteStudents,
    createStudent,
    downloadStudentImportTemplate,
    getStudentsPage,
    importStudents,
    resetStudentPassword,
    updateStudent,
    type BulkDeletePayload
} from "../../api/admin"

interface Student {
    id:number
    student_no:string
    name:string
    weight:number
    selected_course_name:string | null
    selected_course_names:string[]
    selection_status:string | null
}

const students=ref<Student[]>([])
const keyword=ref("")
const appliedKeyword=ref("")
const page=ref(1)
const pageSize=ref(20)
const total=ref(0)
const loading=ref(false)

const tableRef=ref<any>()
const syncingSelection=ref(false)
const selectAllMatching=ref(false)
const selectedIds=ref<Set<number>>(new Set())
const excludedIds=ref<Set<number>>(new Set())
const selectedCount=computed(()=>selectAllMatching.value
    ? Math.max(total.value-excludedIds.value.size, 0)
    : selectedIds.value.size
)

const dialogVisible=ref(false)
const editMode=ref(false)
const editingStudentId=ref(0)
const form=ref({student_no:"", name:"", password:"", weight:0})

const passwordVisible=ref(false)
const passwordLoading=ref(false)
const currentStudent=ref<Student | null>(null)
const passwordForm=ref({new_password:"", confirm_password:""})

const importing=ref(false)
const fileInput=ref<HTMLInputElement>()
const importErrorVisible=ref(false)
const importErrors=ref<string[]>([])

async function syncCurrentPageSelection(){
    await nextTick()
    if(!tableRef.value) return
    syncingSelection.value=true
    tableRef.value.clearSelection()
    for(const student of students.value){
        const selected=selectAllMatching.value
            ? !excludedIds.value.has(student.id)
            : selectedIds.value.has(student.id)
        if(selected) tableRef.value.toggleRowSelection(student, true)
    }
    await nextTick()
    syncingSelection.value=false
}

async function loadStudents(){
    loading.value=true
    try{
        const response=await getStudentsPage(
            appliedKeyword.value,
            page.value,
            pageSize.value
        )
        students.value=response.data.items
        total.value=response.data.total

        const lastPage=Math.max(Math.ceil(total.value/pageSize.value), 1)
        if(page.value>lastPage){
            page.value=lastPage
            await loadStudents()
            return
        }
        await syncCurrentPageSelection()
    }catch(error:any){
        ElMessage.error(error.response?.data?.detail || "获取学生失败")
    }finally{
        loading.value=false
    }
}

function clearSelection(){
    selectAllMatching.value=false
    selectedIds.value=new Set()
    excludedIds.value=new Set()
    tableRef.value?.clearSelection()
}

async function searchStudents(){
    appliedKeyword.value=keyword.value.trim()
    page.value=1
    clearSelection()
    await loadStudents()
}

function handleSelectionChange(selection:Student[]){
    if(syncingSelection.value) return
    const pageIds=new Set(students.value.map(student=>student.id))
    const selectedPageIds=new Set(selection.map(student=>student.id))

    if(selectAllMatching.value){
        const nextExcluded=new Set(excludedIds.value)
        for(const id of pageIds){
            if(selectedPageIds.has(id)) nextExcluded.delete(id)
            else nextExcluded.add(id)
        }
        excludedIds.value=nextExcluded
    }else{
        const nextSelected=new Set(selectedIds.value)
        for(const id of pageIds) nextSelected.delete(id)
        for(const id of selectedPageIds) nextSelected.add(id)
        selectedIds.value=nextSelected
    }
}

async function handleSelectAllMatching(value:boolean){
    selectedIds.value=new Set()
    excludedIds.value=new Set()
    selectAllMatching.value=value
    await syncCurrentPageSelection()
}

function onSelectAllChange(value:string | number | boolean){
    handleSelectAllMatching(Boolean(value))
}

function changePage(value:number){
    page.value=value
    loadStudents()
}

function changePageSize(value:number){
    pageSize.value=value
    page.value=1
    loadStudents()
}

function selectionPayload(ids?:number[]):BulkDeletePayload{
    if(ids){
        return {ids, select_all:false, excluded_ids:[]}
    }
    return {
        ids:Array.from(selectedIds.value),
        select_all:selectAllMatching.value,
        keyword:appliedKeyword.value || undefined,
        excluded_ids:Array.from(excludedIds.value)
    }
}

async function confirmDelete(payload:BulkDeletePayload, count:number){
    if(count===0){
        ElMessage.warning("请先选择要删除的学生")
        return
    }
    try{
        await ElMessageBox.confirm(
            `确认删除 ${count} 名学生吗？对应登录账号和选课记录也会同步删除，操作无法撤销。`,
            "批量删除学生",
            {type:"warning", confirmButtonText:"确认删除", cancelButtonText:"取消"}
        )
        const response=await bulkDeleteStudents(payload)
        ElMessage.success(
            `已删除 ${response.data.deleted_count} 名学生，并清理 ${response.data.selection_deleted_count} 条选课记录`
        )
        clearSelection()
        await loadStudents()
    }catch(error:any){
        if(error!=="cancel"){
            ElMessage.error(error.response?.data?.detail || "删除学生失败")
        }
    }
}

function deleteSelected(){
    confirmDelete(selectionPayload(), selectedCount.value)
}

function deleteStudent(student:Student){
    confirmDelete(selectionPayload([student.id]), 1)
}

function openCreate(){
    editMode.value=false
    editingStudentId.value=0
    form.value={student_no:"", name:"", password:"", weight:0}
    dialogVisible.value=true
}

function openEdit(student:Student){
    editMode.value=true
    editingStudentId.value=student.id
    form.value={
        student_no:student.student_no,
        name:student.name,
        password:"",
        weight:student.weight
    }
    dialogVisible.value=true
}

async function save(){
    if(!form.value.student_no.trim() || !form.value.name.trim()){
        ElMessage.warning("请填写学号和姓名")
        return
    }
    if(!editMode.value && form.value.password.length<6){
        ElMessage.warning("初始密码至少需要 6 位")
        return
    }
    try{
        if(editMode.value){
            await updateStudent(editingStudentId.value, {
                student_no:form.value.student_no.trim(),
                name:form.value.name.trim(),
                weight:form.value.weight
            })
        }else{
            await createStudent({
                ...form.value,
                student_no:form.value.student_no.trim(),
                name:form.value.name.trim()
            })
        }
        ElMessage.success(editMode.value ? "学生信息已更新" : "创建成功")
        dialogVisible.value=false
        await loadStudents()
    }catch(error:any){
        ElMessage.error(error.response?.data?.detail || "创建失败")
    }
}

function openPasswordReset(student:Student){
    currentStudent.value=student
    passwordForm.value={new_password:"", confirm_password:""}
    passwordVisible.value=true
}

async function savePassword(){
    if(passwordForm.value.new_password.length<6){
        ElMessage.warning("新密码至少需要 6 位")
        return
    }
    if(passwordForm.value.new_password!==passwordForm.value.confirm_password){
        ElMessage.warning("两次输入的新密码不一致")
        return
    }
    if(!currentStudent.value) return

    passwordLoading.value=true
    try{
        await resetStudentPassword(
            currentStudent.value.id,
            passwordForm.value.new_password
        )
        ElMessage.success("学生密码已重置")
        passwordVisible.value=false
    }catch(error:any){
        ElMessage.error(error.response?.data?.detail || "密码重置失败")
    }finally{
        passwordLoading.value=false
    }
}

async function downloadTemplate(){
    try{
        const response=await downloadStudentImportTemplate()
        const url=URL.createObjectURL(response.data)
        const link=document.createElement("a")
        link.href=url
        link.download="学生批量导入模板.xlsx"
        link.click()
        URL.revokeObjectURL(url)
    }catch(error:any){
        ElMessage.error(error.response?.data?.detail || "模板下载失败")
    }
}

function chooseImportFile(){
    fileInput.value?.click()
}

async function handleImportFile(event:Event){
    const input=event.target as HTMLInputElement
    const file=input.files?.[0]
    input.value=""
    if(!file) return
    if(!file.name.toLowerCase().endsWith(".xlsx")){
        ElMessage.warning("请选择 .xlsx 文件")
        return
    }

    try{
        await ElMessageBox.confirm(
            `确认导入文件“${file.name}”吗？新学生将使用系统默认初始密码。`,
            "批量导入学生",
            {type:"warning"}
        )
    }catch{
        return
    }

    importing.value=true
    try{
        const response=await importStudents(file)
        ElMessage.success(
            `成功导入 ${response.data.imported_count} 名学生，初始密码为 ${response.data.default_password}`
        )
        page.value=1
        clearSelection()
        await loadStudents()
    }catch(error:any){
        const detail=error.response?.data?.detail
        if(Array.isArray(detail?.errors)){
            importErrors.value=detail.errors
            importErrorVisible.value=true
        }else{
            ElMessage.error(typeof detail==="string" ? detail : "学生导入失败")
        }
    }finally{
        importing.value=false
    }
}

onMounted(loadStudents)
</script>

<template>
<section>
    <div class="page-heading">
        <div>
            <h1>学生管理</h1>
            <p>分页管理学生，可按学号或姓名搜索并批量操作。</p>
        </div>
        <div class="heading-actions">
            <el-input
                v-model="keyword"
                clearable
                placeholder="输入学号或姓名"
                class="search-input"
                @keyup.enter="searchStudents"
                @clear="searchStudents"
            />
            <el-button @click="searchStudents">搜索</el-button>
            <el-button @click="downloadTemplate">下载模板</el-button>
            <el-button :loading="importing" @click="chooseImportFile">批量导入</el-button>
            <el-button type="primary" @click="openCreate">新增学生</el-button>
            <input
                ref="fileInput"
                type="file"
                accept=".xlsx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                class="file-input"
                @change="handleImportFile"
            />
        </div>
    </div>

    <div class="selection-toolbar">
        <el-checkbox
            :model-value="selectAllMatching"
            :disabled="total===0"
            @change="onSelectAllChange"
        >全选当前搜索结果（{{total}} 条）</el-checkbox>
        <span>已选择 {{selectedCount}} 条</span>
        <el-button type="danger" :disabled="selectedCount===0" @click="deleteSelected">
            批量删除
        </el-button>
    </div>

    <el-table
        ref="tableRef"
        v-loading="loading"
        :data="students"
        row-key="id"
        border
        @selection-change="handleSelectionChange"
    >
        <el-table-column type="selection" width="48" reserve-selection />
        <el-table-column prop="id" label="ID" width="70" />
        <el-table-column prop="student_no" label="学号" min-width="120" />
        <el-table-column prop="name" label="姓名" min-width="100" />
        <el-table-column prop="weight" label="权重" width="85" />
        <el-table-column label="已选课程" min-width="130">
            <template #default="scope">
                {{scope.row.selected_course_names?.join("、") || scope.row.selected_course_name || "-"}}
            </template>
        </el-table-column>
        <el-table-column label="操作" width="205" fixed="right">
            <template #default="scope">
                <el-button link @click="openEdit(scope.row)">修改</el-button>
                <el-button type="warning" link @click="openPasswordReset(scope.row)">重置密码</el-button>
                <el-button type="danger" link @click="deleteStudent(scope.row)">删除</el-button>
            </template>
        </el-table-column>
    </el-table>

    <div class="pagination-row">
        <el-pagination
            background
            layout="total, sizes, prev, pager, next, jumper"
            :total="total"
            :current-page="page"
            :page-size="pageSize"
            :page-sizes="[10, 20, 50, 100]"
            @current-change="changePage"
            @size-change="changePageSize"
        />
    </div>

    <el-dialog
        v-model="dialogVisible"
        :title="editMode ? '修改学生' : '创建学生'"
        width="480px"
    >
        <el-form label-width="80px">
            <el-form-item label="学号" required><el-input v-model="form.student_no" /></el-form-item>
            <el-form-item label="姓名" required><el-input v-model="form.name" /></el-form-item>
            <el-form-item v-if="!editMode" label="密码" required>
                <el-input v-model="form.password" type="password" show-password />
            </el-form-item>
            <el-form-item label="权重" required><el-input-number v-model="form.weight" /></el-form-item>
        </el-form>
        <template #footer>
            <el-button @click="dialogVisible=false">取消</el-button>
            <el-button type="primary" @click="save">保存</el-button>
        </template>
    </el-dialog>

    <el-dialog v-model="importErrorVisible" title="导入失败" width="620px">
        <el-alert
            title="文件中存在错误，本次没有导入任何学生"
            type="error"
            show-icon
            :closable="false"
            class="dialog-alert"
        />
        <ul class="import-errors">
            <li v-for="message in importErrors.slice(0, 100)" :key="message">{{message}}</li>
        </ul>
        <p v-if="importErrors.length>100" class="more-errors">
            还有 {{importErrors.length-100}} 条错误未显示，请修正文件后重新导入。
        </p>
    </el-dialog>

    <el-dialog
        v-model="passwordVisible"
        :title="`重置 ${currentStudent?.name || ''} 的密码`"
        width="460px"
    >
        <el-alert
            title="管理员重置密码不需要学生提供旧密码"
            type="warning"
            show-icon
            :closable="false"
            class="dialog-alert"
        />
        <el-form label-width="100px">
            <el-form-item label="新密码" required>
                <el-input v-model="passwordForm.new_password" type="password" show-password />
            </el-form-item>
            <el-form-item label="确认密码" required>
                <el-input
                    v-model="passwordForm.confirm_password"
                    type="password"
                    show-password
                    @keyup.enter="savePassword"
                />
            </el-form-item>
        </el-form>
        <template #footer>
            <el-button @click="passwordVisible=false">取消</el-button>
            <el-button type="primary" :loading="passwordLoading" @click="savePassword">确认重置</el-button>
        </template>
    </el-dialog>
</section>
</template>

<style scoped>
.page-heading{display:flex; align-items:flex-start; justify-content:space-between; gap:24px; margin-bottom:20px}
.page-heading h1{margin-bottom:8px}
.page-heading p{color:#6b7a89}
.heading-actions{display:flex; justify-content:flex-end; align-items:center; gap:8px; flex-wrap:wrap}
.search-input{width:230px}
.file-input{display:none}
.selection-toolbar{display:flex; align-items:center; gap:18px; margin-bottom:14px; padding:12px 16px; border:1px solid #dce5e5; border-radius:10px; background:#fff}
.selection-toolbar span{color:#6b7a89}
.selection-toolbar .el-button{margin-left:auto}
.pagination-row{display:flex; justify-content:flex-end; margin-top:18px}
.dialog-alert{margin-bottom:16px}
.import-errors{max-height:360px; margin:0; padding-left:22px; overflow:auto; color:#b42318}
.import-errors li{margin-bottom:7px}
.more-errors{margin-top:12px; color:#6b7a89}
@media (max-width:800px){
    .page-heading{align-items:stretch; flex-direction:column}
    .heading-actions{justify-content:flex-start}
    .search-input{width:100%}
    .selection-toolbar{align-items:flex-start; flex-direction:column; gap:8px}
    .selection-toolbar .el-button{margin-left:0}
    .pagination-row{justify-content:flex-start; overflow:auto}
}
</style>
