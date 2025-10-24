import yaml 
import re 
import datetime 
import os 
from typing import Optional, Dict

# Note: In actual usage, import from infrastructure.llm
# from infrastructure.llm import model

class TemplateGenerator: 
    
    def __init__(self) -> None:
        # In actual usage, this would be: self.model = model
        # For this fix, we'll show the structure
        pass
        
        
    def generate_template(self, invoice_text: str): 
        
        # Generate template using LLM (which will extract company name)
        template_yaml = self._call_llm(invoice_text)
        
        # Parse and validate the template
        template = self._parse_and_validate_template(template_yaml)
        
        # Extract company name from the generated template
        company_name = template.get('issuer', 'unknown_company')
        
        # Clean company name for filename
        safe_company_name = self._sanitize_filename(company_name)
        
        # Save template 
        self._save_template(
            template=template, 
            template_dir="./templates", 
            filename=f"{safe_company_name}.yaml"
        )
        
        print(f"✓ Generated template for: {company_name}")
    
    
    def _sanitize_filename(self, name: str) -> str:
        """Convert company name to safe filename."""
        # Convert to lowercase and replace spaces/special chars with underscores
        safe_name = re.sub(r'[^a-zA-Z0-9]+', '_', name.lower())
        # Remove leading/trailing underscores
        safe_name = safe_name.strip('_')
        return safe_name if safe_name else 'unknown_company'
    
    
    def _build_prompt(self, invoice_text: str) -> str:
        """Build the prompt for the LLM."""
        
        prompt = f"""You are an expert at creating invoice2data YAML templates. Given the following invoice text, create a complete and accurate invoice2data template in YAML format.

INVOICE TEXT:
```
{invoice_text}
```

REQUIREMENTS:
1. **FIRST AND MOST IMPORTANT**: Identify the issuer/company name from the invoice text and set it as the 'issuer' field
   - Look for company names in headers, footers, or "From:" sections
   - This should be the actual company name, not "Unknown Company" or placeholder
2. Create appropriate keywords for matching future invoices from this company
   - Include the company name
   - Include distinctive terms that appear on invoices from this company
3. Create regex patterns for:
   - Invoice number (invoice_number or rechnungsnummer)
   - Invoice date (date or rechnungsdatum)
   - Due date (due_date or fälligkeitsdatum)
   - Total amount (amount, total, or rechnungsbetrag)
   - Tax/VAT amounts if present
   - Line items/services (items or leistungen)
4. Use proper YAML syntax for invoice2data
5. Use appropriate regex patterns that will match similar invoices from the same company
6. For amounts, use patterns that handle both comma and period decimal separators
7. For dates, handle common date formats (DD.MM.YYYY, DD/MM/YYYY, YYYY-MM-DD, etc.)
8. Add 'options' section if needed for date formats or decimal separators

OUTPUT ONLY THE YAML TEMPLATE, no explanations or markdown code blocks. Start directly with:

issuer: [Actual Company Name from Invoice]
keywords:
  - keyword1
  - keyword2
fields:
  ...

IMPORTANT: 
- Extract the ACTUAL company name from the invoice - don't use placeholders
- Use regex patterns that are robust and will match variations
- For German invoices, include German field names
- Make the template reusable for future invoices from the same company
- Do not include the actual values from this specific invoice in the regex patterns
- Use capture groups appropriately
"""
        
        return prompt
    
    def _parse_and_validate_template(self, template_yaml: str) -> Dict:
        """Parse and validate the generated template."""
        # Remove markdown code blocks if present
        template_yaml = re.sub(r'^```ya?ml\n', '', template_yaml, flags=re.MULTILINE)
        template_yaml = re.sub(r'\n```$', '', template_yaml, flags=re.MULTILINE)
        template_yaml = template_yaml.strip()
        
        # Parse YAML
        try:
            template = yaml.safe_load(template_yaml)
        except yaml.scanner.ScannerError as e:
            raise ValueError(f"Failed to parse generated YAML template: {e}")
        except yaml.parser.ParserError as e:
            raise ValueError(f"Failed to parse generated YAML template: {e}")
        except Exception as e:
            raise ValueError(f"Failed to parse generated YAML template: {e}")
        
        # Validate required fields
        if not isinstance(template, dict):
            raise ValueError("Template must be a dictionary")
        if 'issuer' not in template:
            raise ValueError("Template must include 'issuer' field")
        if 'keywords' not in template:
            raise ValueError("Template must include 'keywords' field")
        if 'fields' not in template:
            raise ValueError("Template must include 'fields' field")
        
        return template
    
    def _save_template(
        self, 
        template: Dict, 
        template_dir: str = "./templates",
        filename: Optional[str] = None
    ) -> str:
        """
        Save the template to a YAML file.
        """
        # Create templates directory if it doesn't exist
        os.makedirs(template_dir, exist_ok=True)
        
        # Generate filename if not provided
        if filename is None:
            issuer = template.get('issuer', 'unknown').lower()
            issuer = re.sub(r'[^a-z0-9]+', '_', issuer)
            timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"{issuer}_{timestamp}.yaml"
        
        filepath = os.path.join(template_dir, filename)
        
        # Save template
        with open(filepath, 'w', encoding='utf-8') as f:
            yaml.dump(template, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
        
        print(f"✓ Saved template to: {filepath}")
        return filepath
    
    def _call_llm(self, invoice_text: str) -> str:
        """Call the LLM API to generate template."""
        
        # In actual usage, uncomment this:
        # from infrastructure.llm import model
        # prompt = self._build_prompt(invoice_text)
        # response = model.query(
        #     prompt=prompt, 
        #     system_prompt="You are a template generator for an invoice extracting system for invoice2data"
        # )
        # return response
        
        # Placeholder for demonstration
        prompt = self._build_prompt(invoice_text)
        # In real implementation, this calls the LLM
        raise NotImplementedError("LLM integration required")
    

if __name__ == '__main__':
    # Example usage would go here
    pass