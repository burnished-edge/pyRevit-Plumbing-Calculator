# -*- coding: utf-8 -*-
import math
import clr
import System
clr.AddReference('PresentationFramework')
from pyrevit import revit, DB, forms, script

doc = revit.doc
app = doc.Application

# ==========================================
# 1. AUTOMATED PARAMETER SETUP
# ==========================================
def setup_plumbing_parameters():
    # 1. Open the user's active Shared Parameter file
    sp_file = app.OpenSharedParameterFile()
    
    if sp_file is None:
        forms.alert("No Shared Parameter file is loaded in Revit. Please load a company file first.", exitscript=True)
        return False
        
    # 2. Find or create the PlumbingCalc group
    group_name = "PlumbingCalc"
    sp_group = sp_file.Groups.get_Item(group_name)
    if sp_group is None:
        sp_group = sp_file.Groups.Create(group_name)
        
    # 3. Define the parameters from your uploaded text file
    params_to_add = {
        "Plumb_Exclude": DB.SpecTypeId.Int.Integer if hasattr(DB.SpecTypeId, 'Int') else DB.ParameterType.Integer,
        "Plumb_OccupancyType": DB.SpecTypeId.String.Text if hasattr(DB.SpecTypeId, 'String') else DB.ParameterType.Text,
        "Plumb_LoadFactor": DB.SpecTypeId.Number if hasattr(DB.SpecTypeId, 'Number') else DB.ParameterType.Number,
        "Plumb_SeatCount": DB.SpecTypeId.Int.Integer if hasattr(DB.SpecTypeId, 'Int') else DB.ParameterType.Integer,
        "Plumb_UnitCount": DB.SpecTypeId.Int.Integer if hasattr(DB.SpecTypeId, 'Int') else DB.ParameterType.Integer
    }
    
    # Target Category: Rooms
    room_cat = doc.Settings.Categories.get_Item(DB.BuiltInCategory.OST_Rooms)
    cat_set = app.Create.NewCategorySet()
    cat_set.Insert(room_cat)
    
    # BuiltInParameterGroup where these will show up in the Properties Panel
    ui_group = DB.GroupTypeId.Data if hasattr(DB, 'GroupTypeId') else DB.BuiltInParameterGroup.PG_DATA
    
    # 4. Open a transaction to bind parameters to the project
    t = DB.Transaction(doc, "Auto-Bind Plumbing Parameters")
    t.Start()
    
    bindings_added = 0
    for param_name, param_type in params_to_add.items():
        # Check if the parameter exists in the Shared Parameter file
        sp_def = sp_group.Definitions.get_Item(param_name)
        
        if sp_def is None:
            # Create it safely with a new GUID
            opt = DB.ExternalDefinitionCreationOptions(param_name, param_type)
            opt.UserModifiable = True
            sp_def = sp_group.Definitions.Create(opt)
            print("Injected into Shared Parameters: {}".format(param_name))
            
        # 5. Check if it is already bound to the project
        binding_map = doc.ParameterBindings
        existing_binding = binding_map.get_Item(sp_def)
        
        if existing_binding is None:
            # Bind it to the Rooms category as an Instance Parameter
            new_binding = app.Create.NewInstanceBinding(cat_set)
            
            # Cross-version compatibility insertion
            binding_map.Insert(sp_def, new_binding, ui_group)
            bindings_added += 1
            print("Bound to Rooms category: {}".format(param_name))
            
    t.Commit()
    
    if bindings_added > 0:
        forms.alert("Successfully auto-bound {} parameters.".format(bindings_added), title="Setup Complete")
        
# ==========================================
# 2. FRACTIONAL MATH & STRING FORMATTING ENGINE
# ==========================================
GROUP_NAMES = {
    'A-1': 'Group A-1 Assembly', 'A-2': 'Group A-2 Assembly', 'A-3': 'Group A-3 Assembly',
    'A-4': 'Group A-4 Assembly', 'A-5': 'Group A-5 Assembly', 'B': 'Group B Business',
    'E': 'Group E Educational', 'F': 'Group F Factory/Industrial', 
    'I-1': 'Group I-1 Institutional', 'I-2-Rooms': 'Group I-2 Institutional', 
    'I-2-Waiting': 'Group I-2 Institutional', 'I-3-Cells': 'Group I-3 Institutional', 
    'I-3-Employee': 'Group I-3 Institutional', 'I-4': 'Group I-4 Institutional', 
    'M': 'Group M Mercantile', 'R-1': 'Group R-1 Residential',
    'R-2-Dorm': 'Group R-2 Residential', 'R-2-Apt': 'Group R-2 Residential',
    'R-2-Employee': 'Group R-2 Residential', 'R-3-Group': 'Group R-3 Residential',
    'R-3-Dwelling': 'Group R-3 Residential', 'R-4': 'Group R-4 Residential', 'S': 'Group S Storage'
}

# Color palette for Occupancy Badges (HTML aesthetic)
GROUP_COLORS = {
    'A-1': '#ffe4e6', 'A-2': '#fef08a', 'A-3': '#d9f99d',
    'A-4': '#bbf7d0', 'A-5': '#a7f3d0', 'B': '#bae6fd',
    'E': '#99f6e4', 'F': '#c7d2fe', 'I-1': '#e0e7ff',
    'I-2-Rooms': '#ddd6fe', 'I-2-Waiting': '#ddd6fe', 
    'I-3-Cells': '#f3e8ff', 'I-3-Employee': '#f3e8ff',
    'I-4': '#fbcfe8', 'M': '#fce7f3', 'R-1': '#fecdd3',
    'R-2-Dorm': '#fecaca', 'R-2-Apt': '#fecaca',
    'R-2-Employee': '#fecaca', 'R-3-Group': '#fecaca',
    'R-3-Dwelling': '#fecaca', 'R-4': '#fecaca', 'S': '#e2e8f0'
}

def run_frac_math(prefix, val, limits, counts, over_divisor):
    if val <= 0: return (0.0, "{}: 0 occupants".format(prefix))
    
    base_val = 0
    base_count = 0
    for limit, count in zip(limits, counts):
        if val <= limit:
            added_counts = count - base_count
            range_span = limit - base_val
            rem_occ = val - base_val
            calc = base_count + rem_occ * (added_counts / float(range_span))
            
            if base_count == 0:
                str_out = "{}: {} occupants * {}/{} = ".format(prefix, val, added_counts, range_span)
            else:
                str_out = "{}: {} occupants = {} fixture(s) with {} - {} = {} Remaining occupants, {} * {}/{} = {:.2f}, Total = ".format(
                    prefix, base_val, base_count, val, base_val, rem_occ, rem_occ, added_counts, range_span, calc - base_count)
            return (calc, str_out)
        base_val = limit
        base_count = count
        
    rem_occ = val - base_val
    calc = base_count + rem_occ / float(over_divisor)
    if base_count == 0:
        str_out = "{}: {} occupants * 1/{} = ".format(prefix, val, over_divisor)
    else:
        str_out = "{}: {} occupants = {} fixture(s) with {} - {} = {} Remaining occupants, {} * 1/{} = {:.2f}, Total = ".format(
            prefix, base_val, base_count, val, base_val, rem_occ, rem_occ, over_divisor, calc - base_count)
    return (calc, str_out)

def run_linear_math(prefix, val, divisor):
    if val <= 0: return (0.0, "{}: 0 occupants".format(prefix))
    calc = val / float(divisor)
    return (calc, "{}: {} occupants * 1/{} = ".format(prefix, val, divisor))

OCC_MAP = {
    'A-1': {'calc': 'seats', 'mWC': ([100,200,400], [1,2,3], 500), 'fWC': ([25,50,100,200,300,400], [1,2,3,4,6,8], 125), 'mUr': ([200,300,400,600], [1,2,3,4], 300), 'mLav': ([200,400,600,750], [1,2,3,4], 250), 'fLav': ([100,200,300,500,750], [1,2,4,5,6], 200), 'df': ([250,500,750], [1,2,3], 500)},
    'A-2': {'calc': 'area', 'fac': 30, 'mWC': ([50,150,300,400], [1,2,3,4], 250), 'fWC': ([25,50,100,200,300,400], [1,2,3,4,6,8], 125), 'mUr': ([200,300,400,600], [1,2,3,4], 300), 'mLav': ([150,200,400], [1,2,3], 250), 'fLav': ([150,200,400], [1,2,4], 200), 'df': ([250,500,750], [1,2,3], 500)},
    'A-2-Seats': {'calc': 'seats', 'mWC': ([50,150,300,400], [1,2,3,4], 250), 'fWC': ([25,50,100,200,300,400], [1,2,3,4,6,8], 125), 'mUr': ([200,300,400,600], [1,2,3,4], 300), 'mLav': ([150,200,400], [1,2,3], 250), 'fLav': ([150,200,400], [1,2,4], 200), 'df': ([250,500,750], [1,2,3], 500)},
    'A-3': {'calc': 'area', 'fac': 30, 'mWC': ([100,200,400], [1,2,3], 500), 'fWC': ([25,50,100,200,300,400], [1,2,3,4,6,8], 125), 'mUr': ([100,200,400,600], [1,2,3,4], 300), 'mLav': ([200,400,600,750], [1,2,3,4], 250), 'fLav': ([100,200,300,500,750], [1,2,4,5,6], 200), 'df': ([250,500,750], [1,2,3], 500)},
    'A-3-Exhibit': {'calc': 'area', 'fac': 30, 'mWC': ([100,200,400], [1,2,3], 500), 'fWC': ([25,50,100,200,300,400], [1,2,3,4,6,8], 125), 'mUr': ([100,200,400,600], [1,2,3,4], 300), 'mLav': ([200,400,600,750], [1,2,3,4], 250), 'fLav': ([100,200,300,500,750], [1,2,4,5,6], 200), 'df': ([250,500,750], [1,2,3], 500)},
    'A-3-Seats': {'calc': 'seats', 'mWC': ([100,200,400], [1,2,3], 500), 'fWC': ([25,50,100,200,300,400], [1,2,3,4,6,8], 125), 'mUr': ([100,200,400,600], [1,2,3,4], 300), 'mLav': ([200,400,600,750], [1,2,3,4], 250), 'fLav': ([100,200,300,500,750], [1,2,4,5,6], 200), 'df': ([250,500,750], [1,2,3], 500)},
    'A-4': {'calc': 'seats', 'mWC': ([100,200,400], [1,2,3], 500), 'fWC': ([25,50,100,200,300,400], [1,2,3,4,6,8], 125), 'mUr': ([100,200,400,600], [1,2,3,4], 300), 'mLav': ([200,400,750], [1,2,3], 250), 'fLav': ([100,200,400,750], [1,2,3,4], 200), 'df': ([250,500,750], [1,2,3], 500)},
    'A-5': {'calc': 'seats', 'mWC': ([100,200,400], [1,2,3], 500), 'fWC': ([25,50,100,200,300,400], [1,2,3,4,6,8], 125), 'mUr': ([100,200,400,600], [1,2,3,4], 300), 'mLav': ([200,400,750], [1,2,3], 250), 'fLav': ([100,200,400,750], [1,2,3,4], 200), 'df': ([250,500,750], [1,2,3], 500)},
    'B': {'calc': 'area', 'fac': 150, 'mWC': ([50,100,200,400], [1,2,3,4], 500), 'fWC': ([15,30,50,100,200,400], [1,2,3,4,8,11], 150), 'mUr': ([100,200,400,600], [1,2,3,4], 300), 'mLav': ([75,150,200,300,400], [1,2,3,4,5], 250), 'fLav': ([50,100,150,200,300,400], [1,2,3,4,5,6], 200), 'df': 150},
    'B-Seats': {'calc': 'seats', 'mWC': ([50,100,200,400], [1,2,3,4], 500), 'fWC': ([15,30,50,100,200,400], [1,2,3,4,8,11], 150), 'mUr': ([100,200,400,600], [1,2,3,4], 300), 'mLav': ([75,150,200,300,400], [1,2,3,4,5], 250), 'fLav': ([50,100,150,200,300,400], [1,2,3,4,5,6], 200), 'df': 150},
    'E': {'calc': 'area', 'fac': 50, 'mWC': 50, 'fWC': 30, 'mUr': 100, 'mLav': 40, 'fLav': 40, 'df': 150},
    'F': {'calc': 'area', 'fac': 500, 'mWC': ([50,75,100], [1,2,3], 40), 'fWC': ([50,75,100], [1,2,3], 40), 'mUr': None, 'mLav': ([50,75,100], [1,2,3], 40), 'fLav': ([50,75,100], [1,2,3], 40), 'df': ([250,500,750], [1,2,3], 500)},
    'I-1': {'calc': 'area', 'fac': 200, 'mWC': 15, 'fWC': 15, 'mUr': None, 'mLav': 15, 'fLav': 15, 'df': 150},
    'I-2-Rooms': { 'calc': 'units' },
    'I-2-Waiting': {'calc': 'area', 'fac': 15, 'mWC': 15, 'fWC': 15, 'mUr': None, 'mLav': 15, 'fLav': 15, 'df': 150},
    'I-3-Cells': { 'calc': 'units' },
    'I-3-Employee': {'calc': 'area', 'fac': 100, 'mWC': ([15,35,55], [1,2,3], 40), 'fWC': ([15,35,55], [1,2,3], 40), 'mUr': None, 'mLav': ([15,35,55], [1,2,3], 40), 'fLav': ([15,35,55], [1,2,3], 40), 'df': 150},
    'I-4': {'calc': 'area', 'fac': 35, 'mWC': 40, 'fWC': 40, 'mUr': None, 'mLav': 40, 'fLav': 40, 'df': 150},
    'M': {'calc': 'area', 'fac': 100, 'mWC': ([100,200,400], [1,2,3], 500), 'fWC': ([100,200,300,400], [1,2,4,6], 200), 'mUr': ([200,400], [0,1], 500), 'mLav': ([200,400], [1,2], 500), 'fLav': ([200,300,400], [1,2,3], 400), 'df': ([250,500,750], [1,2,3], 500)},
    'R-1': { 'calc': 'units' },
    'R-2-Dorm': {'calc': 'area', 'fac': 50, 'mWC': 10, 'fWC': 8, 'mUr': 25, 'mLav': 12, 'fLav': 12, 'df': 150},
    'R-2-Apt': { 'calc': 'units' },
    'R-2-Employee': {'calc': 'area', 'fac': 150, 'mWC': ([15,35,55], [1,2,3], 40), 'fWC': ([15,35,55], [1,2,3], 40), 'mUr': None, 'mLav': 40, 'fLav': 40, 'df': 150},
    'R-3-Group': {'calc': 'area', 'fac': 200, 'mWC': 10, 'fWC': 8, 'mUr': None, 'mLav': 12, 'fLav': 12, 'df': 150},
    'R-3-Dwelling': { 'calc': 'units' },
    'R-4': {'calc': 'area', 'fac': 200, 'mWC': 10, 'fWC': 8, 'mUr': None, 'mLav': 12, 'fLav': 12, 'df': 150},
    'S': {'calc': 'area', 'fac': 4000, 'mWC': ([100,200,400], [1,2,3], 500), 'fWC': ([100,200,400], [1,2,3], 150), 'mUr': None, 'mLav': ([200,400,750], [1,2,3], 500), 'fLav': ([200,400,750], [1,2,3], 500), 'df': ([250,500,750], [1,2,3], 500)}
}

# ==========================================
# 3. DATA BINDING CLASS
# ==========================================
class RoomRecord(object):
    def __init__(self, element, r_id, r_num, r_name, r_area, occ, fac, seat_unit, exclude, level, phase):
        self.Element = element
        self.Id = r_id
        self.Number = r_num
        self.Name = r_name
        self.Area = r_area
        self._occType = occ if occ else 'B'
        self.Exclude = exclude
        self.Level = level
        self.Phase = phase
        self.CalcLoad = 0.0
        
        self.FactorOverride = fac
        self.SeatUnitCount = seat_unit
        self._apply_ux_placeholders()

    @property
    def OccType(self):
        return self._occType

    @OccType.setter
    def OccType(self, value):
        self._occType = value
        self._apply_ux_placeholders()

    def _apply_ux_placeholders(self):
        logic = OCC_MAP.get(self._occType)
        if logic:
            if logic['calc'] == 'area':
                if self.SeatUnitCount != "-": self.SeatUnitCount = "-"
                if self.FactorOverride == "-": self.FactorOverride = ""
            else:
                if self.FactorOverride != "-": self.FactorOverride = "-"
                if self.SeatUnitCount == "-": self.SeatUnitCount = ""

    @property
    def ActiveFactorDisplay(self):
        logic = OCC_MAP.get(self._occType)
        if not logic or logic.get('calc') != 'area': return "-"
        try:
            val = float(self.FactorOverride)
            return str(val) if val > 0 else str(logic.get('fac', '-'))
        except:
            return str(logic.get('fac', '-'))

# ==========================================
# 4. MAIN WINDOW CLASS
# ==========================================
class PlumbingCalcWindow(forms.WPFWindow):
    def __init__(self, xaml_file_name):
        forms.WPFWindow.__init__(self, xaml_file_name)
        self.all_rooms = []
        self.levels = set()
        
        self.gtTotalLoad = 0
        self.gt_mWC = self.gt_fWC = self.gt_mUr = self.gt_mLav = self.gt_fLav = self.gt_df = 0.0
        
        self.OccTypeColumn.ItemsSource = sorted(OCC_MAP.keys())
        self.BulkOccType.ItemsSource = sorted(OCC_MAP.keys())
        
        self.load_rooms()
        self.update_math(refresh_items=True)

    def create_colored_badge(self, text, hex_color):
        """Creates an HTML-style padded badge for WPF TextBlocks"""
        border = System.Windows.Controls.Border()
        border.Background = System.Windows.Media.BrushConverter().ConvertFromString(hex_color)
        border.CornerRadius = System.Windows.CornerRadius(4)
        border.Padding = System.Windows.Thickness(5, 2, 5, 2)
        border.Margin = System.Windows.Thickness(2, -2, 2, -2)
        
        tb = System.Windows.Controls.TextBlock()
        tb.Text = str(text)
        tb.FontWeight = System.Windows.FontWeights.Bold
        tb.Foreground = System.Windows.Media.BrushConverter().ConvertFromString("#0f172a") # Dark text
        
        border.Child = tb
        container = System.Windows.Documents.InlineUIContainer(border)
        container.BaselineAlignment = System.Windows.BaselineAlignment.Center
        return container

    def load_rooms(self):
        rooms = DB.FilteredElementCollector(doc).OfCategory(DB.BuiltInCategory.OST_Rooms).WhereElementIsNotElementType().ToElements()
        error_logs = []
        
        for room in rooms:
            area_param = room.get_Parameter(DB.BuiltInParameter.ROOM_AREA)
            num = room.get_Parameter(DB.BuiltInParameter.ROOM_NUMBER).AsString()
            name = room.get_Parameter(DB.BuiltInParameter.ROOM_NAME).AsString()
            lvl = room.Level.Name if room.Level else "Unknown"
            self.levels.add(lvl)
            
            phase_param = room.get_Parameter(DB.BuiltInParameter.ROOM_PHASE)
            phase_name = phase_param.AsValueString() if (phase_param and phase_param.AsValueString()) else "Unknown"
            
            if area_param and area_param.AsDouble() > 0:
                area_sf = area_param.AsDouble()
                occ_param = room.LookupParameter("Plumb_OccupancyType")
                occ = occ_param.AsString() if (occ_param and occ_param.AsString()) else 'B'
                
                fac_param = room.LookupParameter("Plumb_LoadFactor")
                fac = str(fac_param.AsDouble()) if (fac_param and fac_param.HasValue) else ""
                
                su_param = room.LookupParameter("Plumb_SeatUnitCount")
                su = str(su_param.AsInteger()) if (su_param and su_param.HasValue) else ""
                
                exc_param = room.LookupParameter("Plumb_Exclude")
                exc = (exc_param.AsInteger() == 1) if (exc_param and exc_param.HasValue) else False

                self.all_rooms.append(RoomRecord(room, room.Id, num, name, area_sf, occ, fac, su, exc, lvl, phase_name))
            else:
                error_logs.append("Room {} - {} is unenclosed or unplaced.".format(num, name))
                
        sorted_levels = ["All Levels"] + sorted(list(self.levels))
        self.LevelFilter.ItemsSource = sorted_levels
        self.LevelFilter.SelectedIndex = 0
        
        # Fetch project phases chronologically to set the default to the newest
        project_phases = [p.Name for p in doc.Phases]
        if not project_phases: project_phases = ["Unknown"]
        self.PhaseFilter.ItemsSource = project_phases
        self.PhaseFilter.SelectedItem = project_phases[-1]
        
        if error_logs:
            self.ErrorRoomList.ItemsSource = error_logs
            self.ErrorPanelExpander.Header = "Problem Rooms ({})".format(len(error_logs))
            self.ErrorPanelExpander.Visibility = System.Windows.Visibility.Visible

    def get_safe_float(self, val_str, default_val):
        try:
            val = float(val_str)
            return val if val > 0 else default_val
        except (ValueError, TypeError): return default_val

    def update_math(self, refresh_items=False):
        if refresh_items:
            selected_level = self.LevelFilter.SelectedItem
            selected_phase = self.PhaseFilter.SelectedItem
            
            # Now filters by BOTH Level and Phase
            filtered_rooms = [r for r in self.all_rooms if (selected_level == "All Levels" or r.Level == selected_level) and r.Phase == selected_phase]
            
            current_sorts = list(self.RoomDataGrid.Items.SortDescriptions)
            if not current_sorts:
                filtered_rooms.sort(key=lambda x: x.Number)
                self.RoomDataGrid.ItemsSource = filtered_rooms
            else:
                self.RoomDataGrid.ItemsSource = filtered_rooms
                for sd in current_sorts: self.RoomDataGrid.Items.SortDescriptions.Add(sd)
        else:
            filtered_rooms = self.RoomDataGrid.ItemsSource
            
        self.gtTotalLoad = gtMale = gtFemale = 0
        self.gt_mWC = self.gt_fWC = self.gt_mUr = self.gt_mLav = self.gt_fLav = self.gt_df = 0.0
        
        occ_groups = {}
        
        for rec in filtered_rooms:
            if rec.Exclude:
                rec.CalcLoad = 0.0
                continue
                
            logic = OCC_MAP.get(rec.OccType)
            if not logic: continue
            
            totalOcc = 0.0
            if logic['calc'] in ['seats', 'units']:
                totalOcc = float(self.get_safe_float(rec.SeatUnitCount, 0.0))
            elif logic['calc'] == 'area':
                factor = self.get_safe_float(rec.FactorOverride, logic['fac'])
                totalOcc = float(rec.Area) / factor
            
            rec.CalcLoad = totalOcc
            
            base_occ = rec.OccType
            if base_occ == "A-2-Seats": base_occ = "A-2"
            elif base_occ in ["A-3-Exhibit", "A-3-Seats"]: base_occ = "A-3"
            elif base_occ == "B-Seats": base_occ = "B"
            
            if base_occ not in occ_groups:
                # Force the use of the BASE logic so the UI factors don't scramble
                occ_groups[base_occ] = {'area': 0.0, 'seats': 0.0, 'units': 0.0, 'logic': OCC_MAP[base_occ]}
                
            if logic['calc'] == 'area': occ_groups[base_occ]['area'] += totalOcc
            elif logic['calc'] == 'seats': occ_groups[base_occ]['seats'] += totalOcc
            elif logic['calc'] == 'units': occ_groups[base_occ]['units'] += totalOcc

        # Reset the WPF TextBlock for Inline Bolding and Badges
        self.MathBreakdownText.Text = ""
        
        # Force the overall breakdown text to dark slate/black, overriding the blue Expander default
        self.MathBreakdownText.Foreground = System.Windows.Media.BrushConverter().ConvertFromString("#0f172a")
        
        # Dictionaries to hold the final aggregate math strings for the bottom breakdown
        final_aggregates = {
            'mWC': [], 'fWC': [], 'mUr': [], 'mLav': [], 'fLav': [], 'df': []
        }

        for o_type, data in sorted(occ_groups.items()):
            logic = data['logic']
            a_load = data['area']
            s_load = data['seats']
            u_load = data['units']
            hex_color = GROUP_COLORS.get(o_type, '#e2e8f0') # Default gray if missing
            
            total_unrounded = a_load + s_load + u_load
            t_pop = int(math.ceil(total_unrounded))
            m_pop = int(math.ceil(t_pop / 2.0))
            f_pop = int(math.ceil(t_pop / 2.0))
            
            gtMale += m_pop
            gtFemale += f_pop
            
            # Format: (100 Area + 7 Seats)
            parts = []
            if a_load > 0: parts.append("{:g} Area".format(a_load))
            if s_load > 0: parts.append("{:g} Seats".format(s_load))
            if u_load > 0: parts.append("{:g} Units".format(u_load))
            
            load_str = "({}) = ".format(" + ".join(parts)) if len(parts) > 1 else ""
            
            friendly_name = GROUP_NAMES.get(o_type, "Group " + o_type)
            
            # Print Color-Coded Header Badge for the Group Name
            self.MathBreakdownText.Inlines.Add(self.create_colored_badge(friendly_name, hex_color))
            self.MathBreakdownText.Inlines.Add(System.Windows.Documents.Run("\n"))
            
            run_agg = System.Windows.Documents.Run("Aggregated Base Load: {}{} Occupants -> 50/50 Split rounds up to {} Male & {} Female\n".format(load_str, t_pop, m_pop, f_pop))
            self.MathBreakdownText.Inlines.Add(System.Windows.Documents.Bold(run_agg))
            
            if logic['calc'] != 'units':
                f_map = [('mWC', "WC (M)", m_pop), ('fWC', "WC (F)", f_pop), ('mUr', "Urinals", m_pop), 
                         ('mLav', "Lavatory (M)", m_pop), ('fLav', "Lavatory (F)", f_pop), ('df', "Drinking Fountains", t_pop)]
                
                for f_key, f_prefix, pop_target in f_map:
                    map_val = logic[f_key]
                    if type(map_val) is tuple:
                        calc, str_out = run_frac_math(f_prefix, pop_target, map_val[0], map_val[1], map_val[2])
                    elif type(map_val) is int:
                        calc, str_out = run_linear_math(f_prefix, pop_target, map_val)
                    else:
                        calc, str_out = (0.0, "{}: 0 occupants".format(f_prefix))
                    
                    # Add standard text line up to the equals sign
                    self.MathBreakdownText.Inlines.Add(System.Windows.Documents.Run("  " + str_out))
                    
                    if calc > 0:
                        # Append the colored badge for the final fraction!
                        self.MathBreakdownText.Inlines.Add(self.create_colored_badge("{:.2f}".format(calc), hex_color))
                        final_aggregates[f_key].append({'val': calc, 'color': hex_color})
                    
                    # Capping off the line
                    self.MathBreakdownText.Inlines.Add(System.Windows.Documents.Run("\n"))
                    
                    if f_key == 'mWC': self.gt_mWC += calc
                    if f_key == 'fWC': self.gt_fWC += calc
                    if f_key == 'mUr': self.gt_mUr += calc
                    if f_key == 'mLav': self.gt_mLav += calc
                    if f_key == 'fLav': self.gt_fLav += calc
                    if f_key == 'df': self.gt_df += calc
                    
            self.MathBreakdownText.Inlines.Add(System.Windows.Documents.Run("\n"))

        # --- BUILD THE FINAL COLOR-CODED AGGREGATION AT THE BOTTOM ---
        self.MathBreakdownText.Inlines.Add(System.Windows.Documents.Bold(System.Windows.Documents.Run("FINAL FIXTURE AGGREGATION\n")))
        
        # Using a list of tuples enforces strict ordering, bypassing Python 2.7 dictionary scrambling
        display_keys = [
            ('mWC', "WC (M)"), 
            ('fWC', "WC (F)"), 
            ('mUr', "Urinals"), 
            ('mLav', "Lavatory (M)"), 
            ('fLav', "Lavatory (F)"), 
            ('df', "Drinking Fountains")
        ]
        
        for key, name in display_keys:
            items = final_aggregates[key]
            if not items: continue
            
            self.MathBreakdownText.Inlines.Add(System.Windows.Documents.Run(name + ": "))
            
            total_sum = 0.0
            for i, item in enumerate(items):
                # Add the colored badge
                self.MathBreakdownText.Inlines.Add(self.create_colored_badge("{:.2f}".format(item['val']), item['color']))
                total_sum += item['val']
                
                # Add a "+" sign if it's not the last item
                if i < len(items) - 1:
                    self.MathBreakdownText.Inlines.Add(System.Windows.Documents.Run(" + "))
            
            # Finish the equation with the rounded total
            self.MathBreakdownText.Inlines.Add(System.Windows.Documents.Run(" = {:.2f} ➔ ".format(total_sum)))
            
            run_total = System.Windows.Documents.Run("{} Fixtures\n".format(int(math.ceil(total_sum))))
            run_total.Foreground = System.Windows.Media.BrushConverter().ConvertFromString("#2563eb") # Blue accent
            self.MathBreakdownText.Inlines.Add(System.Windows.Documents.Bold(run_total))

        self.gtTotalLoad = gtMale + gtFemale

        self.lbl_MWC.Text = "Water Closets: {}".format(int(math.ceil(self.gt_mWC)))
        self.lbl_MUr.Text = "Urinals: {}".format(int(math.ceil(self.gt_mUr)))
        self.lbl_MLav.Text = "Lavatories: {}".format(int(math.ceil(self.gt_mLav)))
        self.lbl_FWC.Text = "Water Closets: {}".format(int(math.ceil(self.gt_fWC)))
        self.lbl_FLav.Text = "Lavatories: {}".format(int(math.ceil(self.gt_fLav)))
        self.lbl_AgWC.Text = "Water Closets: {}".format(int(math.ceil(self.gt_mWC + self.gt_fWC)))
        self.lbl_AgLav.Text = "Lavatories: {}".format(int(math.ceil(self.gt_mLav + self.gt_fLav)))
        self.lbl_DF.Text = "Drinking Fountains: {}".format(int(math.ceil(self.gt_df)))
        self.lbl_DesignLoad.Text = "Total Design Load: {}".format(self.gtTotalLoad)
        
        self.RoomDataGrid.Items.Refresh()

    def LevelFilter_SelectionChanged(self, sender, e):
        self.update_math(refresh_items=True)

    def PhaseFilter_SelectionChanged(self, sender, e):
        self.update_math(refresh_items=True)

    def ApplyBulk_Click(self, sender, e):
        selected = self.RoomDataGrid.SelectedItems
        if not selected: return
        
        occ_val = self.BulkOccType.SelectedItem
        fac_val = self.BulkFactor.Text
        su_val = self.BulkSeats.Text
        
        exc_val = None
        if self.BulkExclude.SelectedItem:
            exc_val = self.BulkExclude.SelectedItem.Content
        
        for item in selected:
            if occ_val: item.OccType = occ_val
            if fac_val != "": item.FactorOverride = fac_val
            if su_val != "": item.SeatUnitCount = su_val
            if exc_val == "Yes": item.Exclude = True
            elif exc_val == "No": item.Exclude = False
            
        self.update_math(refresh_items=False)

    def DataGrid_CellEditEnding(self, sender, e):
        def trigger_update():
            self.update_math(refresh_items=False)
        self.Dispatcher.BeginInvoke(System.Action(trigger_update), System.Windows.Threading.DispatcherPriority.ApplicationIdle)
        
    def Checkbox_Click(self, sender, e):
        def trigger_update():
            self.update_math(refresh_items=False)
        self.Dispatcher.BeginInvoke(System.Action(trigger_update), System.Windows.Threading.DispatcherPriority.ApplicationIdle)

    def Calculate_Click(self, sender, e):
        with revit.Transaction("Update Plumbing Calculations"):
            
            for rec in self.all_rooms:
                base_occ_param = rec.Element.LookupParameter("Plumb_BaseOccupants")
                if base_occ_param: base_occ_param.Set(rec.CalcLoad)
                
                occ_type_param = rec.Element.LookupParameter("Plumb_OccupancyType")
                if occ_type_param: occ_type_param.Set(rec.OccType)
                
                su_param = rec.Element.LookupParameter("Plumb_SeatUnitCount")
                if su_param: su_param.Set(self.get_safe_float(rec.SeatUnitCount, 0))
                
                exc_param = rec.Element.LookupParameter("Plumb_Exclude")
                if exc_param: exc_param.Set(1 if rec.Exclude else 0)
                
            target_level = self.LevelFilter.SelectedItem
            if target_level == "All Levels":
                forms.alert("Please select a specific Level from the dropdown before pushing data to a Grand Totals table.", title="Action Required")
                return

            annotations = DB.FilteredElementCollector(doc).OfCategory(DB.BuiltInCategory.OST_GenericAnnotation).WhereElementIsNotElementType().ToElements()
            table_instance = None
            
            for anno in annotations:
                if anno.Symbol.FamilyName == "Plumb_GrandTotals_Table":
                    target_param = anno.LookupParameter("GT_Level_Target")
                    if target_param and target_param.AsString() == target_level:
                        table_instance = anno
                        break
            
            if table_instance:
                table_instance.LookupParameter("GT_Req_MWC").Set(int(math.ceil(self.gt_mWC)))
                table_instance.LookupParameter("GT_Req_FWC").Set(int(math.ceil(self.gt_fWC)))
                table_instance.LookupParameter("GT_Req_MUr").Set(int(math.ceil(self.gt_mUr)))
                table_instance.LookupParameter("GT_Req_MLav").Set(int(math.ceil(self.gt_mLav)))
                table_instance.LookupParameter("GT_Req_FLav").Set(int(math.ceil(self.gt_fLav)))
                table_instance.LookupParameter("GT_Req_AllGenderWC").Set(int(math.ceil(self.gt_mWC + self.gt_fWC)))
                table_instance.LookupParameter("GT_Req_AllGenderLav").Set(int(math.ceil(self.gt_mLav + self.gt_fLav)))
                table_instance.LookupParameter("GT_Req_DF").Set(int(math.ceil(self.gt_df)))
                table_instance.LookupParameter("GT_DesignLoad").Set(self.gtTotalLoad)
                
                forms.alert("Rooms and '{}' Table updated successfully!".format(target_level), title="Success")
            else:
                forms.alert("Rooms updated successfully!\n\nCould not find a Grand Totals table targeting '{}'. Check that your generic annotation family has 'GT_Level_Target' set to match the level name.".format(target_level), title="Rooms Updated")

# ==========================================
# 5. SCRIPT EXECUTION
# ==========================================
auto_bind_plumbing_parameters()

window = PlumbingCalcWindow('PlumbingCalc_ui.xaml')
window.ShowDialog()
