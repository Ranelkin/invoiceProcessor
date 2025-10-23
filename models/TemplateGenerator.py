import pylibyaml
import yaml 
import re 
import datetime 
import os 
from typing import Optional, Dict
from infrastructure.llm import model

class TemplateGenerator: 
    
    def __init__(self) -> None:
        self.model = model 
        
        
    def generate_template(self, 
                          invoice_text: str, 
                          company_name: str = None): 
        
        # Generate template using LLM
        template_yaml = self._call_llm(invoice_text, company_name)
        
        # Parse and validate the template
        template = self._parse_and_validate_template(template_yaml)
        
        #Save template 
        self._save_template(template=template, template_dir="./templates", filename=company_name+".yaml")
    
    
    
    def _build_prompt(self, invoice_text: str, company_name: Optional[str]) -> str:
        """Build the prompt for the LLM."""
        
        company_context = f"\nThe company/issuer name is: {company_name}" if company_name else ""
        
        prompt = f"""You are an expert at creating invoice2data YAML templates. Given the following invoice text, create a complete and accurate invoice2data template in YAML format.

{company_context}

INVOICE TEXT:
```
{invoice_text}
```

REQUIREMENTS:
1. Identify the issuer/company name and create appropriate keywords for matching
2. Create regex patterns for:
   - Invoice number (rechnungsnummer or invoice_number)
   - Invoice date (rechnungsdatum or date)
   - Due date (fälligkeitsdatum or due_date)
   - Total amount (rechnungsbetrag or amount or total)
   - Tax/VAT amounts if present
   - Line items/services (leistungen or items)
3. Use proper YAML syntax for invoice2data
4. Include the 'issuer' field with the company name
5. Use appropriate regex patterns that will match similar invoices from the same company
6. For amounts, use patterns that handle both comma and period decimal separators
7. For dates, handle common date formats (DD.MM.YYYY, DD/MM/YYYY, etc.)
8. Add 'options' section if needed for date formats or decimal separators

OUTPUT ONLY THE YAML TEMPLATE, no explanations or markdown code blocks. Start directly with:

issuer: [Company Name]
keywords:
  - keyword1
  - keyword2
fields:
  ...

IMPORTANT: 
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
            template = yaml.load(template_yaml, Loader=yaml.CSafeLoader)
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
        
        Args:
            template: The template dictionary
            template_dir: Directory to save templates
            filename: Optional filename (will be auto-generated if not provided)
        
        Returns:
            Path to the saved template file
        """
        # Create templates directory if it doesn't exist
        os.makedirs(template_dir, exist_ok=True)
        
        # Generate filename if not provided
        if filename is None:
            issuer = template.get('issuer', 'unknown').lower()
            issuer = re.sub(r'[^a-z0-9]+', '_', issuer)
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"{issuer}_{timestamp}.yml"
        
        filepath = os.path.join(template_dir, filename)
        
        # Save template
        with open(filepath, 'w', encoding='utf-8') as f:
            yaml.dump(template, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
        
        return filepath
    
    def _call_llm(self, invoice_text: str, company_name: Optional[str]) -> str:
        """Call the LLM API to generate template."""
        
        prompt = self._build_prompt(invoice_text, company_name)
        response = model.query(prompt=prompt, system_prompt="You are a template generator for an invoice ecstracting system for invoice2data")
        return response
    

if __name__ == '__main__':
    from ..infrastructure.ocr import *
    from dotenv import load_dotenv
    import os 
    generator = TemplateGenerator()
    load_dotenv()
    p = os.environ.get("TEST_PATH")
    out = preprocess(p)
    text = ocr_document(out)
    print(f"Read in text:\n{text}")
    generator.generate_template(text, "Amazon_Web_Services")