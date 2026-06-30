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
def auto_bind_plumbing_parameters():
    sp_file = app.OpenSharedParameterFile()
    if not sp_file: return
    plumb_group = sp_file.Groups.get_Item("PlumbingCalc")
    if not plumb_group: return
    
    category_set = app.Create.NewCategorySet()
    room_category = doc.Settings.Categories.get_Item(DB.BuiltInCategory.OST_Rooms)
    category_set.Insert(room_category)

    binding_map = doc.ParameterBindings
    bindings_added = 0

    with revit.Transaction("Auto-Bind Plumbing Parameters"):
        for sp_def in plumb_group.Definitions:
            if not binding_map.get_Item(sp_def):
                instance_binding = app.Create.NewInstanceBinding(category_set)
                if binding_map.Insert(sp_def, instance_binding, DB.GroupTypeId.Data):
                    bindings_added += 1

    if bindings_added > 0:
        forms.alert("Successfully auto-bound {} parameters.".format(bindings_added), title="Setup Complete")

# ==========================================
# 2. FRACTIONAL MATH & STRING FORMATTING ENGINE
# ==========================================
def run_frac_math(val, limits, counts, over_divisor):
    if val <= 0: return (0.0, "0.00")
    
    base_val = 0
    base_count = 0.0
    for limit, count in zip(limits, counts):
        if val <= limit:
            added_counts = count - base_count
            range_span = limit - base_val
            calc = base_count + (val - base_val) * (added_counts / float(range_span))
            return (calc, "{} + ({}/{} of {}) = {:.2f}".format(base_count, added_counts, range_span, val - base_val, calc))
        base_val = limit
        base_count = count
        
    over = val - base_val
    calc = base_count + over / float(over_divisor)
    return (calc, "{} + ({}/{}) = {:.2f}".format(base_count, over, over_divisor, calc))

def run_linear_math(val, divisor):
    if val <= 0: return (0.0, "0.00")
    calc = val / float(divisor)
    return (calc, "{}/{} = {:.2f}".format(val, divisor, calc))

# Simplified logic map (Area, Seats, Units)
OCC_MAP = {
    'A-1': {'calc': 'seats', 'mWC': ([100,200,400], [1,2,3], 500), 'fWC': ([25,50,100,200,300,400], [1,2,3,4,6,8], 125), 'mUr': ([200,300,400,600], [1,2,3,4], 300), 'mLav': ([200,400,600,750], [1,2,3,4], 250), 'fLav': ([100,200,300,500,750], [1,2,4,5,6], 200), 'df': ([250,500,750], [1,2,3], 500)},
    'A-2': {'calc': 'area', 'fac': 30, 'mWC': ([50,150,300,400], [1,2,3,4], 250), 'fWC': ([25,50,100,200,300,400], [1,2,3,4,6,8], 125), 'mUr': ([200,300,400,600], [1,2,3,4], 300), 'mLav': ([150,200,400], [1,2,3], 250), 'fLav': ([150,200,400], [1,2,4], 200), 'df': ([250,500,750], [1,2,3], 500)},
    'A-2-Seats': {'calc': 'seats', 'mWC': ([50,150,300,400], [1,2,3,4], 250), 'fWC': ([25,50,100,200,300,400], [1,2,3,4,6,8], 125), 'mUr': ([200,300,400,600], [1,2,3,4], 300), 'mLav': ([150,200,400], [1,2,3], 250), 'fLav': ([150,200,400], [1,2,4], 200), 'df': ([250,500,750], [1,2,3], 500)},
    'A-3-Exhibit': {'calc': 'area', 'fac': 30, 'mWC': ([100,200,400], [1,2,3], 500), 'fWC': ([25,50,100,200,300,400], [1,2,3,4,6,8], 125), 'mUr': ([100,200,400,600], [1,2,3,4], 300), 'mLav': ([200,400,600,750], [1,2,3,4], 250), 'fLav': ([100,200,300,500,750], [1,2,4,5,6], 200), 'df': ([250,500,750], [1,2,3], 500)},
    'A-3-Seats': {'calc': 'seats', 'mWC': ([100,200,400], [1,2,3], 500), 'fWC': ([25,50,100,200,300,400], [1,2,3,4,6,8], 125), 'mUr': ([100,200,400,600], [1,2,3,4], 300), 'mLav': ([200,400,600,750], [1,2,3,4], 250), 'fLav': ([100,200,300,500,750], [1,2,4,5,6], 200), 'df': ([250,500,750], [1,2,3], 500)},
    'A-4': {'calc': 'seats', 'mWC': ([100,200,400], [1,2,3], 500), 'fWC': ([25,50,100,200,300,400], [1,2,3,4,6,8], 125), 'mUr': ([100,200,400,600], [1,2,3,4], 300), 'mLav': ([200,400,750], [1,2,3], 250), 'fLav': ([100,200,400,750], [1,2,3,4], 200), 'df': ([250,500,750], [1,2,3], 500)},
    'A-5': {'calc': 'seats', 'mWC': ([100,200,400], [1,2,3], 500), 'fWC': ([25,50,100,200,300,400], [1,2,3,4,6,8], 125), 'mUr': ([100,200,400,600], [1,2,3,4], 300), 'mLav': ([200,400,750], [1,2,3], 250), 'fLav': ([100,200,400,750], [1,2,3,4], 200), 'df': ([250,500,750], [1,2,3], 500)},
    'B': {'calc': 'area', 'fac': 150, 'mWC': ([50,100,200,400], [1,2,3,4], 500), 'fWC': ([15,30,50,100,200,400], [1,2,3,4,8,11], 150), 'mUr': ([100,200,400,600], [1,2,3,4], 300), 'mLav': ([75,150,200,300,400], [1,2,3,4,5], 250), 'fLav': ([50,100,150,200,300,400], [1,2,3,4,5,6], 200), 'df': 150},
    'B-Seats': {'calc': 'seats', 'mWC': ([50,100,200,400], [1,2,3,4], 500), 'fWC': ([15,30,50,100,200,400], [1,2,3,4,8,11], 150), 'mUr': ([100,200,400,600], [1,2,3,4], 300), 'mLav': ([75,150,200,300,400], [1,2,3,4,5], 250), 'fLav': ([50,100,150,200,300,400], [1,2,3,4,5,6], 200), 'df': 150},
    'E': {'calc': 'area', 'fac': 50, 'mWC': 50, 'fWC': 30, 'mUr': 100, 'mLav': 40, 'fLav': 40, 'df': 150},
    'M': {'calc': 'area', 'fac': 100, 'mWC': ([100,200,400], [1,2,3], 500), 'fWC': ([100,200,300,400], [1,2,4,6], 200), 'mUr': ([200,400], [0,1], 500), 'mLav': ([200,400], [1,2], 500), 'fLav': ([200,300,400], [1,2,3], 400), 'df': ([250,500,750], [1,2,3], 500)},
    'I-2-Rooms': { 'calc': 'units' },
    'I-3-Cells': { 'calc': 'units' },
    'R-1': { 'calc': 'units' },
    'R-2-Apt': { 'calc': 'units' },
    'R-3-Dwelling': { 'calc': 'units' }
}

# ==========================================
# 3. DATA BINDING CLASS
# ==========================================
class RoomRecord(object):
    def __init__(self, element, r_id, r_num, r_name, r_area, occ, fac, seat_unit, exclude, level):
        self.Element = element
        self.Id = r_id
        self.Number = r_num
        self.Name = r_name
        self.Area = r_area
        self._occType = occ if occ else 'B'
        self.Exclude = exclude
        self.Level = level
        self.CalcLoad = 0.0  # Raw fractional load
        
        # Initialize UX fields cleanly
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
        """Automatically blanks out inapplicable parameters with a '-' based on occupancy type."""
        logic = OCC_MAP.get(self._occType)
        if logic:
            if logic['calc'] == 'area':
                self.SeatUnitCount = "-"
            else:
                self.FactorOverride = "-"

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
        self.update_math()

    def load_rooms(self):
        rooms = DB.FilteredElementCollector(doc).OfCategory(DB.BuiltInCategory.OST_Rooms).WhereElementIsNotElementType().ToElements()
        error_logs = []
        
        for room in rooms:
            area_param = room.get_Parameter(DB.BuiltInParameter.ROOM_AREA)
            num = room.get_Parameter(DB.BuiltInParameter.ROOM_NUMBER).AsString()
            name = room.get_Parameter(DB.BuiltInParameter.ROOM_NAME).AsString()
            lvl = room.Level.Name if room.Level else "Unknown"
            self.levels.add(lvl)
            
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

                self.all_rooms.append(RoomRecord(room, room.Id, num, name, area_sf, occ, fac, su, exc, lvl))
            else:
                error_logs.append("Room {} - {} is unenclosed or unplaced.".format(num, name))
                
        sorted_levels = ["All Levels"] + sorted(list(self.levels))
        self.LevelFilter.ItemsSource = sorted_levels
        self.LevelFilter.SelectedIndex = 0
        
        if error_logs:
            self.ErrorRoomList.ItemsSource = error_logs
            self.ErrorPanelExpander.Header = "Problem Rooms ({})".format(len(error_logs))
            self.ErrorPanelExpander.Visibility = System.Windows.Visibility.Visible

    def get_safe_float(self, val_str, default_val):
        try:
            val = float(val_str)
            return val if val > 0 else default_val
        except (ValueError, TypeError): return default_val

    def update_math(self):
        selected_level = self.LevelFilter.SelectedItem
        filtered_rooms = [r for r in self.all_rooms if selected_level == "All Levels" or r.Level == selected_level]
        self.RoomDataGrid.ItemsSource = filtered_rooms
        
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
            
            # NOTE: Leaving occupants strictly fractional until aggregation per code
            if logic['calc'] in ['seats', 'units']:
                totalOcc = float(self.get_safe_float(rec.SeatUnitCount, 0.0))
            elif logic['calc'] == 'area':
                factor = self.get_safe_float(rec.FactorOverride, logic['fac'])
                totalOcc = float(rec.Area) / factor
            
            rec.CalcLoad = totalOcc
            
            if rec.OccType not in occ_groups:
                occ_groups[rec.OccType] = {'total': 0.0, 'm': 0, 'f': 0}
                
            occ_groups[rec.OccType]['total'] += totalOcc

        math_strings = []
        for o_type, pops in occ_groups.items():
            logic = OCC_MAP[o_type]
            
            # Floor-wide Occupancy Aggregation Round-Up Event
            t_pop = int(math.ceil(pops['total']))
            m_pop = int(math.ceil(t_pop / 2.0))
            f_pop = int(math.ceil(t_pop / 2.0))
            
            gtMale += m_pop
            gtFemale += f_pop
            
            header = "\n[ {} ] Base Aggregated Load: {} ({}M / {}F)\n".format(o_type, t_pop, m_pop, f_pop)
            lines = [header]
            
            # Note: Units-only occupancies skip fixture calculations in this loop
            if logic['calc'] != 'units':
                for f_key, pop_target in [('mWC', m_pop), ('fWC', f_pop), ('mUr', m_pop), ('mLav', m_pop), ('fLav', f_pop), ('df', t_pop)]:
                    map_val = logic[f_key]
                    if type(map_val) is tuple:
                        calc, str_out = run_frac_math(pop_target, map_val[0], map_val[1], map_val[2])
                    elif type(map_val) is int:
                        calc, str_out = run_linear_math(pop_target, map_val)
                    else:
                        calc, str_out = (0.0, "0.00")
                    
                    lines.append("  {:5} : {}".format(f_key, str_out))
                    
                    if f_key == 'mWC': self.gt_mWC += calc
                    if f_key == 'fWC': self.gt_fWC += calc
                    if f_key == 'mUr': self.gt_mUr += calc
                    if f_key == 'mLav': self.gt_mLav += calc
                    if f_key == 'fLav': self.gt_fLav += calc
                    if f_key == 'df': self.gt_df += calc
                
            math_strings.append("\n".join(lines) + "\n")

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
        self.MathBreakdownText.Text = "Aggregate M-WC: {:.2f} | Aggregate F-WC: {:.2f}\n".format(self.gt_mWC, self.gt_fWC) + "".join(math_strings)
        
        self.RoomDataGrid.Items.Refresh()

    def LevelFilter_SelectionChanged(self, sender, e):
        self.update_math()

    def ApplyBulk_Click(self, sender, e):
        selected = self.RoomDataGrid.SelectedItems
        if not selected: return
        
        occ_val = self.BulkOccType.SelectedItem
        fac_val = self.BulkFactor.Text
        su_val = self.BulkSeats.Text
        
        for item in selected:
            if occ_val: item.OccType = occ_val
            if fac_val != "": item.FactorOverride = fac_val
            if su_val != "": item.SeatUnitCount = su_val
        self.update_math()

    def DataGrid_CellEditEnding(self, sender, e):
        def trigger_update():
            self.update_math()
        self.Dispatcher.BeginInvoke(System.Action(trigger_update))

    def Calculate_Click(self, sender, e):
        with revit.Transaction("Update Plumbing Calculations"):
            
            # 1. Push precisely calculated fractions & settings back to the Room parameters
            for rec in self.all_rooms:
                base_occ_param = rec.Element.LookupParameter("Plumb_BaseOccupants")
                if base_occ_param: base_occ_param.Set(rec.CalcLoad)
                
                occ_type_param = rec.Element.LookupParameter("Plumb_OccupancyType")
                if occ_type_param: occ_type_param.Set(rec.OccType)
                
                su_param = rec.Element.LookupParameter("Plumb_SeatUnitCount")
                if su_param: su_param.Set(self.get_safe_float(rec.SeatUnitCount, 0))
                
                exc_param = rec.Element.LookupParameter("Plumb_Exclude")
                if exc_param: exc_param.Set(1 if rec.Exclude else 0)
                
            # 2. Update the Target Grand Totals Generic Annotation Family
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