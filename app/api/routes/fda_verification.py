# app/api/routes/fda_verification.py
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query
from fastapi.responses import StreamingResponse
import pandas as pd
import io
from datetime import datetime
from typing import Optional, List

from app.core.deps import get_current_active_user
from app.db.deps import DBSessionDep
from app.crud import fda_verification as crud

router = APIRouter(
    prefix="/api/fda",
    tags=["FDA Verification"],
    dependencies=[Depends(get_current_active_user)]  # 🔐 LOGIN REQUIRED BY DEFAULT
)


# ==================== DOWNLOAD TEMPLATE ====================
@router.get("/download-template")
async def download_template():
    """
    Download Excel template for FDA drug registration upload
    """
    try:
        # Create sample data
        sample_data = {
            'registration_number': ['DR-XYZ123456', 'DR-ABC789012'],
            'generic_name': ['Paracetamol', 'Ibuprofen'],
            'brand_name': ['Biogesic', 'Advil'],
            'dosage_strength': ['500mg', '200mg'],
            'dosage_form': ['Tablet', 'Tablet'],
            'classification': ['OTC', 'OTC'],
            'packaging': ['Box of 10 tablets', 'Bottle of 100 tablets'],
            'pharmacologic_category': ['Analgesic', 'NSAID'],
            'manufacturer': ['Company A', 'Company B'],
            'country': ['Philippines', 'USA'],
            'trader': ['Trader A', 'Trader B'],
            'importer': ['Importer A', 'Importer B'],
            'distributor': ['Distributor A', 'Distributor B'],
            'app_type': ['New', 'Renewal'],
            'issuance_date': ['2024-01-15', '2024-02-20'],
            'expiry_date': ['2029-01-15', '2029-02-20']
        }
        
        # Create DataFrame
        df = pd.DataFrame(sample_data)
        
        # Create Excel file in memory
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='FDA Drug Registration')
            
            # Get the worksheet
            worksheet = writer.sheets['FDA Drug Registration']
            
            # Set column widths
            column_widths = {
                'A': 20, 'B': 40, 'C': 30, 'D': 15, 'E': 20,
                'F': 15, 'G': 40, 'H': 30, 'I': 40, 'J': 20,
                'K': 40, 'L': 40, 'M': 40, 'N': 15, 'O': 15, 'P': 15
            }
            for col, width in column_widths.items():
                worksheet.column_dimensions[col].width = width
        
        output.seek(0)
        
        # Return as downloadable file
        return StreamingResponse(
            output,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={
                "Content-Disposition": f"attachment; filename=FDA_Drug_Registration_Template_{datetime.now().strftime('%Y%m%d')}.xlsx"
            }
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate template: {str(e)}"
        )


# ==================== UPLOAD EXCEL ====================
@router.post("/upload-excel")
async def upload_excel(
    file: UploadFile = File(...),
    uploaded_by: Optional[str] = Query(None, description="Username of uploader")
):
    """
    Upload Excel file with FDA drug registration data
    """
    # Validate file type
    if not file.filename.endswith(('.xlsx', '.xls')):
        raise HTTPException(
            status_code=400,
            detail="Invalid file type. Please upload an Excel file (.xlsx or .xls)"
        )
    
    try:
        # Read Excel file
        contents = await file.read()
        df = pd.read_excel(io.BytesIO(contents))
        
        # Validate required columns
        required_columns = ['registration_number']
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            raise HTTPException(
                status_code=400,
                detail=f"Missing required columns: {', '.join(missing_columns)}"
            )
        
        # Remove empty rows
        df = df.dropna(subset=['registration_number'])
        
        if len(df) == 0:
            raise HTTPException(
                status_code=400,
                detail="No valid data found in Excel file"
            )
        
        # Prepare data for bulk insert
        drugs_data = []
        for index, row in df.iterrows():
            data = {
                'registration_number': str(row.get('registration_number', '')).strip(),
                'generic_name': str(row.get('generic_name', '')) if pd.notna(row.get('generic_name')) else None,
                'brand_name': str(row.get('brand_name', '')) if pd.notna(row.get('brand_name')) else None,
                'dosage_strength': str(row.get('dosage_strength', '')) if pd.notna(row.get('dosage_strength')) else None,
                'dosage_form': str(row.get('dosage_form', '')) if pd.notna(row.get('dosage_form')) else None,
                'classification': str(row.get('classification', '')) if pd.notna(row.get('classification')) else None,
                'packaging': str(row.get('packaging', '')) if pd.notna(row.get('packaging')) else None,
                'pharmacologic_category': str(row.get('pharmacologic_category', '')) if pd.notna(row.get('pharmacologic_category')) else None,
                'manufacturer': str(row.get('manufacturer', '')) if pd.notna(row.get('manufacturer')) else None,
                'country': str(row.get('country', '')) if pd.notna(row.get('country')) else None,
                'trader': str(row.get('trader', '')) if pd.notna(row.get('trader')) else None,
                'importer': str(row.get('importer', '')) if pd.notna(row.get('importer')) else None,
                'distributor': str(row.get('distributor', '')) if pd.notna(row.get('distributor')) else None,
                'app_type': str(row.get('app_type', '')) if pd.notna(row.get('app_type')) else None,
                'issuance_date': row.get('issuance_date') if pd.notna(row.get('issuance_date')) else None,
                'expiry_date': row.get('expiry_date') if pd.notna(row.get('expiry_date')) else None,
                'uploaded_by': uploaded_by
            }
            
            # Convert dates if needed
            if data['issuance_date'] and isinstance(data['issuance_date'], str):
                data['issuance_date'] = datetime.strptime(data['issuance_date'], '%Y-%m-%d').date()
            if data['expiry_date'] and isinstance(data['expiry_date'], str):
                data['expiry_date'] = datetime.strptime(data['expiry_date'], '%Y-%m-%d').date()
            
            drugs_data.append(data)
        
        # Call CRUD function
        result = crud.bulk_create_drugs(drugs_data)
        
        return {
            "status": "success" if result['failed'] == 0 else "partial_success",
            "message": f"Upload completed. {result['successful']} records inserted, {result['failed']} failed.",
            "total_rows": len(df),
            "successful": result['successful'],
            "failed": result['failed'],
            "errors": result['errors']
        }
        
    except pd.errors.EmptyDataError:
        raise HTTPException(
            status_code=400,
            detail="Excel file is empty"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to process Excel file: {str(e)}"
        )


# ==================== GET ALL DRUGS ====================
@router.get("/drugs")
async def get_all_drugs(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(10, ge=1, le=100, description="Items per page"),
    search: Optional[str] = Query(None, description="Search by registration number, generic name, or brand name"),
    include_deleted: bool = Query(False, description="Include soft-deleted records")
):
    """
    Get all FDA drug registrations with pagination and search
    """
    try:
        result = crud.get_all_drugs(
            page=page,
            page_size=page_size,
            search=search,
            include_deleted=include_deleted
        )
        
        return {
            "status": "success",
            "data": result['drugs'],
            "pagination": {
                "page": result['page'],
                "page_size": result['page_size'],
                "total": result['total'],
                "total_pages": result['total_pages'],
                "has_next": result['has_next'],
                "has_prev": result['has_prev']
            }
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve drugs: {str(e)}"
        )


# ==================== EXPORT DRUGS TO EXCEL ====================
# ⚠️ IMPORTANT: This route MUST come BEFORE /drugs/{drug_id}
@router.get("/drugs/export")
async def export_drugs_to_excel(
    search: Optional[str] = Query(None, description="Search by registration number, generic name, or brand name"),
    include_deleted: bool = Query(False, description="Include soft-deleted records")
):
    """
    Export all FDA drug registrations to Excel (no pagination limit)
    """
    try:
        # Get ALL records (no pagination)
        result = crud.export_all_drugs(
            search=search,
            include_deleted=include_deleted
        )
        
        drugs_data = result.get('drugs', [])
        
        if not drugs_data:
            raise HTTPException(
                status_code=404,
                detail="No data found to export"
            )
        
        # Convert to DataFrame
        df = pd.DataFrame(drugs_data)
        
        # Reorder columns for better readability
        column_order = [
            'id',
            'registration_number',
            'generic_name',
            'brand_name',
            'dosage_strength',
            'dosage_form',
            'classification',
            'packaging',
            'pharmacologic_category',
            'manufacturer',
            'country',
            'trader',
            'importer',
            'distributor',
            'app_type',
            'issuance_date',
            'expiry_date',
            'uploaded_by',
            'date_uploaded',
            'created_at',
            'updated_at',
        ]
        
        # Only include columns that exist in the dataframe
        available_columns = [col for col in column_order if col in df.columns]
        df = df[available_columns]
        
        # Create Excel file in memory
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='FDA Drug Registrations')
            
            # Get the worksheet
            worksheet = writer.sheets['FDA Drug Registrations']
            
            # Set column widths
            column_widths = {
                'A': 10,  # id
                'B': 20,  # registration_number
                'C': 40,  # generic_name
                'D': 30,  # brand_name
                'E': 15,  # dosage_strength
                'F': 20,  # dosage_form
                'G': 15,  # classification
                'H': 40,  # packaging
                'I': 30,  # pharmacologic_category
                'J': 40,  # manufacturer
                'K': 20,  # country
                'L': 40,  # trader
                'M': 40,  # importer
                'N': 40,  # distributor
                'O': 15,  # app_type
                'P': 15,  # issuance_date
                'Q': 15,  # expiry_date
                'R': 20,  # uploaded_by
                'S': 20,  # date_uploaded
                'T': 20,  # created_at
                'U': 20,  # updated_at
            }
            
            for col_letter, width in column_widths.items():
                worksheet.column_dimensions[col_letter].width = width
            
            # Style header row
            from openpyxl.styles import Font, PatternFill
            header_fill = PatternFill(start_color="4CAF50", end_color="4CAF50", fill_type="solid")
            header_font = Font(bold=True, color="FFFFFF")
            
            for cell in worksheet[1]:
                cell.fill = header_fill
                cell.font = header_font
        
        output.seek(0)
        
        # Return as downloadable file
        filename = f"FDA_Drugs_Export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        
        return StreamingResponse(
            output,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={
                "Content-Disposition": f"attachment; filename={filename}"
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to export drugs: {str(e)}"
        )


# ==================== GET DRUG BY ID ====================
@router.get("/drugs/{drug_id}")
async def get_drug_by_id(drug_id: int):
    """
    Get a specific FDA drug registration by ID
    """
    try:
        drug = crud.get_drug_by_id(drug_id)
        
        if not drug:
            raise HTTPException(
                status_code=404,
                detail=f"Drug registration with ID {drug_id} not found"
            )
        
        return {
            "status": "success",
            "data": drug
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve drug: {str(e)}"
        )


# ==================== VERIFY REGISTRATION NUMBER ====================
@router.get("/verify/{registration_number}")
async def verify_registration(registration_number: str):
    """
    Verify if a registration number exists and is valid
    """
    try:
        result = crud.verify_registration(registration_number)
        
        if not result['found']:
            return {
                "status": "not_found",
                "message": "Registration number not found",
                "is_valid": False,
                "data": None
            }
        
        return {
            "status": "found",
            "message": "Registration number is valid" if result['is_valid'] else "Registration number is expired",
            "is_valid": result['is_valid'],
            "data": result['data']
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to verify registration: {str(e)}"
        )


# ==================== UPDATE DRUG ====================
@router.put("/drugs/{drug_id}")
async def update_drug(drug_id: int, update_data: dict):
    """
    Update a drug registration
    """
    try:
        result = crud.update_drug(drug_id, update_data)
        
        if not result['success']:
            raise HTTPException(
                status_code=404 if result['error'] == "Drug not found" else 400,
                detail=result['error']
            )
        
        return {
            "status": "success",
            "message": result['message']
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update drug: {str(e)}"
        )


# ==================== DELETE DRUG (SOFT DELETE) ====================
@router.delete("/drugs/{drug_id}")
async def delete_drug(drug_id: int):
    """
    Soft delete a drug registration
    """
    try:
        result = crud.delete_drug(drug_id)
        
        if not result['success']:
            raise HTTPException(
                status_code=404,
                detail=result['error']
            )
        
        return {
            "status": "success",
            "message": result['message']
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete drug: {str(e)}"
        )